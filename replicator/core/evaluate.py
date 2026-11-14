"""Evaluate a BuildProgram into meshes with manifold3d. Pure CPU, no GPU anywhere.

Internal geometry is Y-up. manifold3d builds cylinders and extrusions along +Z, so those get turned to +Y here.
Results are cached by op hash, so an edit recomputes only that op and what depends on it.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from pathlib import Path

from manifold3d import CrossSection, Manifold, Mesh, OpType

from .program import COMBINERS, check, op_hash, op_inputs

Z_TO_Y = (-90.0, 0.0, 0.0)  # rotate +Z onto +Y
AXIS_ROT = {"y": Z_TO_Y, "z": (0.0, 0.0, 0.0), "x": (0.0, 90.0, 0.0)}


class EvalError(ValueError):
    pass


class _Status:
    name = "NotManifold"


class _RawMeshData:
    def __init__(self, vp, tri):
        self.vert_properties = vp
        self.tri_verts = tri


class RawMesh:
    """Imported geometry that is not a closed manifold (most downloaded GLBs). It can be shown, moved, exploded and
    exported to GLB, but not used in booleans, hulls or STL. Implements the subset of Manifold the app uses."""

    def __init__(self, V: np.ndarray, F: np.ndarray, N: np.ndarray | None = None):
        self.V = np.asarray(V, np.float64)
        self.F = np.asarray(F, np.uint32)
        self.N = N

    def _new(self, V):
        return RawMesh(V, self.F)

    def is_empty(self):
        return len(self.F) == 0

    def bounding_box(self):
        lo, hi = self.V.min(0), self.V.max(0)
        return (*lo.tolist(), *hi.tolist())

    def volume(self):
        a, b, c = (self.V[self.F[:, i]] for i in range(3))
        return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)

    def status(self):
        return _Status()

    def genus(self):
        return -1

    def num_tri(self):
        return len(self.F)

    def translate(self, t):
        return self._new(self.V + np.asarray(t, np.float64))

    def scale(self, s):
        return self._new(self.V * np.asarray(s, np.float64))

    def mirror(self, n):
        n = np.asarray(n, np.float64)
        n = n / (np.linalg.norm(n) or 1)
        V = self.V - 2 * np.outer(self.V @ n, n)
        return RawMesh(V, self.F[:, ::-1].copy())

    def rotate(self, r):
        rx, ry, rz = np.radians(np.asarray(r, np.float64))
        cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
        Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
        Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
        Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
        return self._new(self.V @ (Rz @ Ry @ Rx).T)  # X, then Y, then Z (manifold's order)

    def calculate_normals(self, _idx=0, _angle=0.0):
        a, b, c = (self.V[self.F[:, i]] for i in range(3))
        fn = np.cross(b - a, c - a)
        vn = np.zeros_like(self.V)
        for i in range(3):
            np.add.at(vn, self.F[:, i], fn)
        vn /= np.linalg.norm(vn, axis=1, keepdims=True) + 1e-12
        return RawMesh(self.V, self.F, vn)

    def to_mesh(self):
        vp = self.V if self.N is None else np.hstack([self.V, self.N])
        return _RawMeshData(vp.astype(np.float32), self.F)


def load_asset(base: Path | None, rel: str):
    if base is None:
        raise EvalError("mesh assets need a project folder (open the program from disk)")
    path = (base / rel).resolve()
    if base.resolve() not in path.parents:
        raise EvalError("mesh asset must live inside the project folder")
    if not path.exists():
        raise EvalError(f"mesh asset {rel} not found")
    d = np.load(path)
    V, F = np.asarray(d["V"], np.float32), np.asarray(d["F"], np.uint32)
    try:
        m = Manifold(Mesh(vert_properties=np.ascontiguousarray(V), tri_verts=np.ascontiguousarray(F)))
        if not m.is_empty() and m.status().name == "NoError":
            return m
    except Exception:  # noqa: BLE001 - any failure means "not a manifold": fall back to the raw mesh
        pass
    return RawMesh(V, F)


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


def _axis_index(axis) -> int:
    """'x'/'y'/'z' or an axis-aligned vector like [0, 0, 1] (models write both)."""
    if isinstance(axis, str) and axis.lower().lstrip("+-") in ("x", "y", "z"):
        return "xyz".index(axis.lower().lstrip("+-"))
    if isinstance(axis, (list, tuple)) and len(axis) == 3:
        a = [abs(float(v)) for v in axis]
        if sorted(a)[:2] == [0.0, 0.0] and max(a) > 0:
            return a.index(max(a))
    raise EvalError("axis must be x, y, z or an axis-aligned vector like [0, 1, 0]")


def _place(m: Manifold, p: dict) -> Manifold:
    if "scale" in p:
        m = m.scale(_vec3(p["scale"], "scale"))
    if "rotate" in p:
        m = m.rotate(_vec3(p["rotate"], "rotate"))
    if "translate" in p:
        m = m.translate(_vec3(p["translate"], "translate"))
    return m


EXT_PRIMITIVES: dict = {}
EXT_MODIFIERS: dict = {}


def build_primitive(kind: str, p: dict, base: Path | None = None) -> Manifold:
    if kind in EXT_PRIMITIVES:
        return EXT_PRIMITIVES[kind][2](p)
    if kind == "mesh":
        return load_asset(base, str(p["asset"]))
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
    if kind in EXT_MODIFIERS:
        _need_manifold(m, kind)
        return EXT_MODIFIERS[kind][2](p, m)
    if kind == "transform":
        return m
    if kind != "array":
        _need_manifold(m, kind)
    elif isinstance(m, RawMesh):
        raise EvalError("array needs a closed solid; this imported mesh is not watertight")
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
            idx = _axis_index(p.get("axis", "y"))
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


def _need_manifold(m, what: str):
    if isinstance(m, RawMesh):
        raise EvalError(f"{what} needs a closed solid; this imported mesh is not watertight (show, move and explode "
                        "work, CSG does not)")


def build_combiner(kind: str, p: dict, ms: list[Manifold]) -> Manifold:
    for m in ms:
        _need_manifold(m, kind)
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
    hash: str = ""
    component: str = ""

    def arrays(self) -> tuple[np.ndarray, np.ndarray]:
        """(positions float32 [n,3], indices uint32 [m,3]) for the viewport and exporters."""
        mesh = self.manifold.to_mesh()
        return np.asarray(mesh.vert_properties[:, :3], np.float32), np.asarray(mesh.tri_verts, np.uint32)


class Evaluator:
    def __init__(self, base: Path | None = None):
        self.base = base
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
                    m = build_primitive(kind, p, self.base)
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

    def trim(self, limit: int) -> None:
        """Bound the cache: drop the oldest results beyond `limit` (dicts keep insertion order)."""
        extra = len(self._cache) - limit
        if extra > 0:
            for h in list(self._cache)[:extra]:
                del self._cache[h]

    def step(self, program: dict, k: int | None = None) -> list[Shape]:
        """The visible shapes after step k (0-based, inclusive). None = the finished build."""
        ops = program["ops"]
        k = len(ops) - 1 if k is None else max(0, min(k, len(ops) - 1))
        sub = dict(program, ops=ops[: k + 1])
        built, hashes = self.run(sub)
        consumed = {i for op in sub["ops"] for i in op_inputs(op)}
        # a leaf inherits material from its first input chain when it has none of its own
        mat_of: dict[str, str | None] = {}
        comp = component_map(sub)
        for op in sub["ops"]:
            ins = op_inputs(op)
            mat_of[op["id"]] = op.get("material") or (mat_of.get(ins[0]) if ins else None)
        return [Shape(op["id"], op.get("label", op["id"]), op.get("part", op["id"]), mat_of[op["id"]],
                      built[op["id"]], hashes[op["id"]], comp[op["id"]])
                for op in sub["ops"] if op["id"] not in consumed]


def component_map(program: dict) -> dict[str, str]:
    """op id -> component id: its own `component`, else its first input's, else its `part`, else its id."""
    out: dict[str, str] = {}
    for op in program["ops"]:
        ins = op_inputs(op)
        out[op["id"]] = op.get("component") or (out.get(ins[0]) if ins else None) or op.get("part") or op["id"]
    return out


def bounds(shapes: list[Shape]) -> tuple[list[float], list[float]]:
    lo = [math.inf] * 3
    hi = [-math.inf] * 3
    for s in shapes:
        b = s.manifold.bounding_box()
        lo = [min(lo[i], b[i]) for i in range(3)]
        hi = [max(hi[i], b[i + 3]) for i in range(3)]
    return lo, hi


def _register_extensions() -> None:
    from . import ops_advanced
    from .program import register
    register(ops_advanced.PRIMITIVES, ops_advanced.MODIFIERS)
    EXT_PRIMITIVES.update(ops_advanced.PRIMITIVES)
    EXT_MODIFIERS.update(ops_advanced.MODIFIERS)


_register_extensions()
