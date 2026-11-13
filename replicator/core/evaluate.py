"""Evaluate a BuildProgram into meshes with manifold3d. Pure CPU, no GPU anywhere.

Internal geometry is Y-up. manifold3d builds cylinders and extrusions along +Z, so those get turned to +Y here.
Results are cached by op hash, so an edit recomputes only that op and what depends on it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from manifold3d import CrossSection, Manifold, OpType

from .program import COMBINERS, check, op_hash, op_inputs

Z_TO_Y = (-90.0, 0.0, 0.0)  # rotate +Z onto +Y
AXIS_ROT = {"y": Z_TO_Y, "z": (0.0, 0.0, 0.0), "x": (0.0, 90.0, 0.0)}


class EvalError(ValueError):
    pass


def _segs(p: dict, default: int = 64) -> int:
    return int(p.get("segments", default))


def _vec3(v, name: str) -> list[float]:
    if isinstance(v, (int, float)):
        return [float(v)] * 3
    if not (isinstance(v, (list, tuple)) and len(v) == 3):
        raise EvalError(f"{name} must be a number or [x, y, z]")
    return [float(x) for x in v]


def _poly(points, name: str) -> list[list[float]]:
    if not isinstance(points, list) or len(points) < 3:
        raise EvalError(f"{name} needs at least 3 [x, y] points")
    out = []
    for pt in points:
        if not (isinstance(pt, (list, tuple)) and len(pt) == 2):
            raise EvalError(f"{name}: every point is [x, y]")
        out.append([float(pt[0]), float(pt[1])])
    return out


def _place(m: Manifold, p: dict) -> Manifold:
    if "scale" in p:
        m = m.scale(_vec3(p["scale"], "scale"))
    if "rotate" in p:
        m = m.rotate(_vec3(p["rotate"], "rotate"))
    if "translate" in p:
        m = m.translate(_vec3(p["translate"], "translate"))
    return m


def build_primitive(kind: str, p: dict) -> Manifold:
    if kind == "box":
        return Manifold.cube(_vec3(p["size"], "size"), center=bool(p.get("center", True)))
    if kind == "cylinder":
        r0 = float(p["radius"])
        r1 = float(p.get("radius_top", r0))
        return Manifold.cylinder(float(p["height"]), r0, r1, _segs(p), center=True).rotate(Z_TO_Y)
    if kind == "sphere":
        return Manifold.sphere(float(p["radius"]), _segs(p))
    if kind == "torus":
        R, r = float(p["major_radius"]), float(p["minor_radius"])
        if r >= R:
            raise EvalError("torus minor_radius must be smaller than major_radius")
        circle = CrossSection.circle(r, _segs(p, 32)).translate((R, 0.0))
        return Manifold.revolve(circle, _segs(p)).rotate(Z_TO_Y)
    if kind == "capsule":
        h, r = float(p["height"]), float(p["radius"])
        a = Manifold.sphere(r, _segs(p)).translate((0, -h / 2, 0))
        b = Manifold.sphere(r, _segs(p)).translate((0, h / 2, 0))
        return Manifold.batch_hull([a, b])
    if kind == "extrude":
        polys = [_poly(p["points"], "points")] + [_poly(h, "holes") for h in p.get("holes", [])]
        cs = CrossSection(polys)
        st = p.get("scale_top", [1.0, 1.0])
        st = [float(st)] * 2 if isinstance(st, (int, float)) else [float(st[0]), float(st[1])]
        h = float(p["height"])
        m = Manifold.extrude(cs, h, n_divisions=int(abs(float(p.get("twist", 0))) // 10),
                             twist_degrees=float(p.get("twist", 0.0)), scale_top=st)
        m = m.translate((0, 0, -h / 2))
        axis = p.get("axis", "y")
        if axis not in AXIS_ROT:
            raise EvalError("extrude axis must be x, y or z")
        return m.rotate(AXIS_ROT[axis])
    if kind == "revolve":
        # points are [radius, height] pairs, a lathe profile around the Y axis
        pts = _poly(p["points"], "points")
        if any(x < 0 for x, _ in pts):
            raise EvalError("revolve points are [radius, height]; radius must be >= 0")
        return Manifold.revolve(CrossSection([pts]), _segs(p), float(p.get("degrees", 360.0))).rotate(Z_TO_Y)
    raise EvalError(f"unknown primitive {kind}")


def build_modifier(kind: str, p: dict, m: Manifold) -> Manifold:
    if kind == "transform":
        return m
    if kind == "array":
        mode, n = p["mode"], int(p["count"])
        if n < 1 or n > 256:
            raise EvalError("array count must be 1..256")
        if mode == "linear":
            off = _vec3(p.get("offset", [10, 0, 0]), "offset")
            parts = [m.translate([off[0] * i, off[1] * i, off[2] * i]) for i in range(n)]
        elif mode == "radial":
            ang = float(p.get("angle", 360.0))
            step = ang / n if ang >= 360 else ang / max(n - 1, 1)
            axis = p.get("axis", "y")
            idx = {"x": 0, "y": 1, "z": 2}.get(axis)
            if idx is None:
                raise EvalError("radial array axis must be x, y or z")
            parts = []
            for i in range(n):
                r = [0.0, 0.0, 0.0]
                r[idx] = step * i
                parts.append(m.rotate(r))
        else:  # mirror: the original plus its reflection
            normal = _vec3(p.get("plane", [1, 0, 0]), "plane")
            parts = [m, m.mirror(normal)]
        return Manifold.batch_boolean(parts, OpType.Add)
    if kind == "smooth":
        levels = int(p.get("levels", 2))
        if levels < 1 or levels > 4:
            raise EvalError("smooth levels must be 1..4")
        return m.smooth_out(float(p.get("sharp_angle", 60.0))).refine(2 ** levels)
    if kind == "round":
        r = float(p["radius"])
        if r <= 0:
            raise EvalError("round radius must be > 0")
        # rounded edges via a Minkowski sum; the part grows by r on every side (true bevel = Blender worker)
        return m.minkowski_sum(Manifold.sphere(r, _segs(p, 12)))
    if kind == "shell":
        t = float(p["thickness"])
        lo, hi = np.array(m.bounding_box()[:3]), np.array(m.bounding_box()[3:])
        size = hi - lo
        if t <= 0 or t * 2 >= size.min():
            raise EvalError("shell thickness must be > 0 and under half the smallest size")
        inner = m.scale(((size - 2 * t) / size).tolist())
        c0, c1 = (lo + hi) / 2, None
        lo2, hi2 = np.array(inner.bounding_box()[:3]), np.array(inner.bounding_box()[3:])
        c1 = (lo2 + hi2) / 2
        return m - inner.translate((c0 - c1).tolist())
    raise EvalError(f"unknown modifier {kind}")


def build_combiner(kind: str, p: dict, ms: list[Manifold]) -> Manifold:
    if kind == "boolean":
        op = {"union": OpType.Add, "difference": OpType.Subtract, "intersection": OpType.Intersect}[p["mode"]]
        return Manifold.batch_boolean(ms, op)
    if kind == "hull":
        return Manifold.batch_hull(ms)
    if kind == "group":
        return Manifold.compose(ms)
    raise EvalError(f"unknown combiner {kind}")


@dataclass
class Shape:
    id: str
    label: str
    part: str
    material: str | None
    manifold: Manifold

    def arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """(positions float32 [n,3], indices uint32 [m,3]) for the viewport and exporters."""
        mesh = self.manifold.to_mesh()
        return np.asarray(mesh.vert_properties[:, :3], np.float32), np.asarray(mesh.tri_verts, np.uint32)


class Evaluator:
    def __init__(self):
        self._cache: dict[str, Manifold] = {}
        self.last_hits = 0
        self.last_misses = 0

    def run(self, program: dict) -> tuple[dict[str, Manifold], dict[str, str]]:
        check(program)
        out: dict[str, Manifold] = {}
        hashes: dict[str, str] = {}
        self.last_hits = self.last_misses = 0
        for op in program["ops"]:
            ins = op_inputs(op)
            h = op_hash(op, [hashes[i] for i in ins])
            hashes[op["id"]] = h
            if h in self._cache:
                out[op["id"]] = self._cache[h]
                self.last_hits += 1
                continue
            self.last_misses += 1
            kind, p = op["op"], op.get("params", {})
            try:
                if not ins:
                    m = build_primitive(kind, p)
                elif kind in COMBINERS:
                    m = build_combiner(kind, p, [out[i] for i in ins])
                else:
                    m = build_modifier(kind, p, out[ins[0]])
                m = _place(m, p)
            except EvalError as e:
                raise EvalError(f"op {op['id']} ({kind}): {e}") from None
            except (KeyError, TypeError, ValueError) as e:
                raise EvalError(f"op {op['id']} ({kind}): bad params ({e})") from None
            if m.is_empty():
                raise EvalError(f"op {op['id']} ({kind}): result is empty (a difference removed everything, "
                                "or the shapes do not overlap)")
            self._cache[h] = m
            out[op["id"]] = m
        return out, hashes

    def step(self, program: dict, k: int | None = None) -> list[Shape]:
        """The visible shapes after step k (0-based, inclusive). None = the finished build."""
        ops = program["ops"]
        k = len(ops) - 1 if k is None else max(0, min(k, len(ops) - 1))
        sub = dict(program, ops=ops[: k + 1])
        built, _ = self.run(sub)
        consumed = {i for op in sub["ops"] for i in op_inputs(op)}
        # a leaf inherits material from its first input chain when it has none of its own
        mat_of: dict[str, str | None] = {}
        for op in sub["ops"]:
            ins = op_inputs(op)
            mat_of[op["id"]] = op.get("material") or (mat_of.get(ins[0]) if ins else None)
        return [Shape(op["id"], op.get("label", op["id"]), op.get("part", op["id"]), mat_of[op["id"]],
                      built[op["id"]]) for op in sub["ops"] if op["id"] not in consumed]


def bounds(shapes: list[Shape]) -> tuple[list[float], list[float]]:
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for s in shapes:
        b = s.manifold.bounding_box()
        lo = [min(lo[i], b[i]) for i in range(3)]
        hi = [max(hi[i], b[i + 3]) for i in range(3)]
    return lo, hi
