"""Accuracy critic: measured checks that catch the ways a local model gets an assembly wrong.

A program can be valid and still be a bad build: a ring spun around the wrong axis, a part floating in the air, a
pump buried inside the casing where nobody can see it. Every check here measures the built geometry, so an issue is
an observation, not an opinion. `fix` issues go back to the model on a critique round; `warn` issues are shown.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass

import numpy as np

from .assembly import Component
from .evaluate import Evaluator, RawMesh, Shape
from .program import op_inputs
from .physics import properties

AXISYM = {"cylinder", "tube", "torus", "revolve", "nozzle", "rotor", "capsule", "gear", "helix"}
CLIP_SHARE = 0.25        # overlap, as a share of the smaller part, that reads as parts passing through each other
BURIED_SHARE = 0.95
SIZE_WARN = 0.15         # built size off the blueprint by more than this on any axis: shown
SIZE_FIX = 0.40          # by more than this: goes back to the model (the lamp that came out twice its planned size)
STOP = {"the", "and", "with", "for", "assembly", "set", "main", "unit", "part", "parts", "system", "section"}


@dataclass(frozen=True)
class Issue:
    kind: str
    severity: str          # "fix" | "warn"
    subject: str           # component id, or "" for the whole object
    message: str

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass
class Build:
    program: dict
    shapes: list[Shape]
    comps: list[Component]

    @property
    def size(self) -> np.ndarray:
        lo = np.min([c.lo for c in self.comps], axis=0)
        hi = np.max([c.hi for c in self.comps], axis=0)
        return hi - lo

    def label(self, cid: str) -> str:
        return next((c.label for c in self.comps if c.id == cid), cid)


def _solid(s: Shape) -> bool:
    return not isinstance(s.manifold, RawMesh)


def _box(s: Shape) -> tuple[np.ndarray, np.ndarray]:
    b = s.manifold.bounding_box()
    return np.array(b[:3]), np.array(b[3:])


def _gap(alo, ahi, blo, bhi) -> float:
    return float(np.linalg.norm(np.maximum(0.0, np.maximum(alo - bhi, blo - ahi))))


def _boxes(shapes: list[Shape]) -> tuple[np.ndarray, np.ndarray]:
    bb = np.array([s.manifold.bounding_box() for s in shapes], dtype=np.float64).reshape(-1, 6)
    return bb[:, :3], bb[:, 3:]


def floating(b: Build) -> list[Issue]:
    if len(b.comps) < 2:
        return []
    tol = 0.01 * float(np.linalg.norm(b.size))
    lo, hi = np.array([c.lo for c in b.comps]), np.array([c.hi for c in b.comps])
    d = np.maximum(0.0, np.maximum(lo[:, None, :] - hi[None, :, :], lo[None, :, :] - hi[:, None, :]))
    gap = np.linalg.norm(d, axis=2)
    np.fill_diagonal(gap, np.inf)
    out = []
    for i, c in enumerate(b.comps):
        j = int(np.argmin(gap[i]))
        if gap[i, j] > tol:
            out.append(Issue("floating", "fix", c.id, f"{c.label} floats free: it touches no other part "
                             f"(nearest is {b.comps[j].label}, {gap[i, j]:.0f} {b.program.get('units', 'mm')} away). "
                             "Move it until it is attached."))
    return out


def _grown(s: Shape, tol: float) -> Shape:
    lo, hi = _box(s)
    c, size = (lo + hi) / 2, np.maximum(hi - lo, 1e-9)
    return Shape(s.id, s.label, s.part, s.material, s.manifold.translate((-c).tolist()).scale(((size + 2 * tol) / size).tolist()).translate(c.tolist()), s.hash, s.component)


def cavity_floating(b: Build) -> list[Issue]:
    """A part whose bounding box sits inside another part's box passes the box test even when it hangs loose in a
    hollow body; grow it by the contact tolerance and test the real solids."""
    if len(b.comps) < 2:
        return []
    tol = 0.01 * float(np.linalg.norm(b.size))
    by_comp: dict[str, list[Shape]] = {}
    for s in b.shapes:
        if _solid(s):
            by_comp.setdefault(s.component, []).append(s)
    lo, hi = np.array([c.lo for c in b.comps]), np.array([c.hi for c in b.comps])
    inside = np.all(lo[:, None, :] >= lo[None, :, :] - tol, axis=2) & np.all(hi[:, None, :] <= hi[None, :, :] + tol, axis=2)
    np.fill_diagonal(inside, False)
    out = []
    for i, c in enumerate(b.comps):
        mine = by_comp.get(c.id)
        if not mine or not inside[i].any():
            continue
        host = b.comps[int(np.argmax(inside[i]))]
        grown = [_grown(s, tol) for s in mine]
        others = [(_box(t), t) for o in b.comps if o is not c for t in by_comp.get(o.id, [])]
        touches = any(_gap(*_box(g), *tb) == 0.0 and (g.manifold ^ t.manifold).volume() > 0
                      for g in grown for tb, t in others)
        if not touches:
            out.append(Issue("floating", "fix", c.id, f"{c.label} hangs loose inside {host.label}: it touches "
                             "nothing, so it would fall to the bottom of the cavity. Attach it with a bracket or "
                             "move it against a wall."))
    return out


def _pairs(b: Build):
    solids = [s for s in b.shapes if _solid(s)]
    if len(solids) < 2:
        return
    lo, hi = _boxes(solids)
    vol = np.array([s.manifold.volume() for s in solids])
    comp = np.array([s.component for s in solids])
    for i in range(len(solids) - 1):
        j = np.arange(i + 1, len(solids))
        inter = np.minimum(hi[i], hi[j]) - np.maximum(lo[i], lo[j])
        touch = np.all(inter >= 0.0, axis=1) & (comp[j] != comp[i])
        cap = np.prod(np.maximum(inter, 0.0), axis=1)
        keep = touch & (cap >= CLIP_SHARE * np.minimum(vol[i], vol[j]))
        for k in j[keep]:
            yield solids[i], solids[k]


PLUGS = {"pipe", "capsule"}
PLUG_WORDS = re.compile(r"\b(duct|line|pipe|hose|shaft|strut|rod|pin|bolt|inlet|outlet|axle|spindle|tube)s?\b", re.I)
SLENDER = 4.0


def _plugs_in(b_ops: dict, small: Shape, big: Shape) -> bool:
    """Pipes, shafts and struts are meant to run into the part they connect: that overlap is contact, not clipping."""
    if b_ops.get(small.id, {}).get("op") in PLUGS or b_ops.get(big.id, {}).get("op") in PLUGS:
        return True
    if PLUG_WORDS.search(small.label) or PLUG_WORDS.search(big.label):
        return True
    lo, hi = _box(small)
    d = np.sort(hi - lo)
    return bool(d[2] >= SLENDER * max(d[1], 1e-9))


def overlaps(b: Build) -> list[Issue]:
    out, buried = [], set()
    ops = {o["id"]: o for o in b.program["ops"]}
    for s, t in _pairs(b):
        shared = (s.manifold ^ t.manifold).volume()
        if shared <= 0:
            continue
        small, big = (s, t) if s.manifold.volume() <= t.manifold.volume() else (t, s)
        share = shared / max(small.manifold.volume(), 1e-9)
        if share >= BURIED_SHARE and small.component not in buried:
            buried.add(small.component)
            out.append(Issue("buried", "fix", small.component, f"{small.label} is buried inside {big.label} "
                             f"({share:.0%} of it is inside solid material) and can never be seen. Hollow "
                             f"{big.label} or move the part out."))
        elif CLIP_SHARE <= share < BURIED_SHARE and not _plugs_in(ops, small, big):
            out.append(Issue("clipping", "warn", small.component, f"{small.label} passes through {big.label} "
                             f"({share:.0%} of it overlaps)."))
    return out


COPY_OVERLAP = 0.15
THIN_WALL = 0.001


def _closure(ops: dict, oid: str) -> list[dict]:
    seen: list[str] = []

    def walk(i: str):
        for j in op_inputs(ops[i]):
            walk(j)
        if i not in seen:
            seen.append(i)
    walk(oid)
    return [ops[i] for i in seen]


def array_copies(b: Build) -> list[Issue]:
    """The copies of an array should sit apart; copies that interpenetrate fuse into one lump (a radial array whose
    source is on the axis stacks every copy in the same place)."""
    ops = {o["id"]: o for o in b.program["ops"]}
    out = []
    for s in b.shapes:
        op = ops.get(s.id, {})
        p = op.get("params", {})
        if op.get("op") != "array" or not _solid(s) or "scale" in p or len(op_inputs(op)) != 1:
            continue
        n = 2 if p.get("mode") == "mirror" else int(p.get("count", 1))
        if n < 2:
            continue
        try:
            src = Evaluator().step({"version": 1, "units": b.program.get("units", "mm"),
                                    "ops": _closure(ops, op_inputs(op)[0])})
        except Exception:  # noqa: BLE001 - a broken source is reported by the build, not here
            continue
        if not src or not _solid(src[-1]):
            continue
        lost = 1.0 - s.manifold.volume() / (n * src[-1].manifold.volume())
        if lost > COPY_OVERLAP:
            out.append(Issue("array_overlap", "fix", s.component, f"The {n} copies in {s.label} overlap each other "
                             f"({lost:.0%} of their volume is shared). Increase the offset or angle, or move the "
                             "source off the pivot."))
    return out


def thin_wall(b: Build) -> list[Issue]:
    """A hollow body whose wall is a sliver next to its size will not render, print or survive a load."""
    out = []
    for o in b.program["ops"]:
        p = o.get("params", {})
        if o.get("op") != "tube" or not isinstance(p.get("wall"), (int, float)):
            continue
        reach = max(float(p.get("radius", 0)), float(p.get("radius_top", 0)), float(p.get("height", 0)) / 2)
        if reach > 0 and p["wall"] < THIN_WALL * reach:
            out.append(Issue("thin_wall", "warn", next((s.component for s in b.shapes if s.id == o["id"]), ""),
                             f"{o.get('label', o['id'])} has a {p['wall']:g} {b.program.get('units', 'mm')} wall on a "
                             f"body {reach:.0f} across: a sliver. Make the wall at least {THIN_WALL * reach:.1f}."))
    return out


def _axis(op: dict) -> np.ndarray:
    rx, ry, rz = np.radians(op.get("params", {}).get("rotate", [0, 0, 0]))
    cx, sx, cy, sy, cz, sz = np.cos(rx), np.sin(rx), np.cos(ry), np.sin(ry), np.cos(rz), np.sin(rz)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx @ np.array([0.0, 1.0, 0.0])


def off_axis(b: Build) -> list[Issue]:
    """A ring, casing or rotor that sits on the body's centre line must spin around the same axis as the body."""
    ops = {o["id"]: o for o in b.program["ops"]}
    sym = [s for s in b.shapes if ops.get(s.id, {}).get("op") in AXISYM and _solid(s)]
    if len(sym) < 2:
        return []
    body = max(sym, key=lambda s: s.manifold.volume())
    axis = _axis(ops[body.id])
    lo, hi = _box(body)
    centre, reach = (lo + hi) / 2, 0.5 * float(np.max(hi - lo))
    out = []
    for s in sym:
        if s is body:
            continue
        slo, shi = _box(s)
        d = (slo + shi) / 2 - centre
        off_line = float(np.linalg.norm(d - np.dot(d, axis) * axis))
        a = _axis(ops[s.id])
        if off_line < 0.1 * reach and abs(float(np.dot(a, axis))) < 0.94:
            name = "XYZ"[int(np.argmax(np.abs(axis)))]
            out.append(Issue("off_axis", "fix", s.component, f"{s.label} sits on the centre line of {body.label} but "
                             f"spins around a different axis; {body.label} runs along {name}. Rotate it to match."))
    return out


def size(b: Build) -> list[Issue]:
    want = (b.program.get("blueprint") or {}).get("dimensions")
    if not (isinstance(want, list) and len(want) == 3 and all(isinstance(v, (int, float)) and v > 0 for v in want)):
        return []
    got = b.size
    share = [abs(got[i] - want[i]) / want[i] for i in range(3)]
    off = [i for i in range(3) if share[i] > SIZE_WARN]
    if not off:
        return []
    fmt = lambda v: " x ".join(f"{x:.0f}" for x in v)  # noqa: E731
    worst = max(share)
    axes = ", ".join(f"{'XYZ'[i]} {'+' if got[i] > want[i] else '-'}{share[i]:.0%}" for i in off)
    return [Issue("size", "fix" if worst > SIZE_FIX else "warn", "",
                  f"Built {fmt(got)} but the blueprint plans {fmt(want)} ({axes}). Scale the parts that "
                  "overshoot, or correct the plan if the build is right.")]


ROOF_WORDS = ("roof",)
PITCHED = re.compile(r"\b(gable|gabled|pitched|hip|hipped|ridge|saltbox|a-frame|mansard)\b")
BUTTERFLY = re.compile(r"\b(butterfly|v-shaped|inverted)\b")
ANGLE = re.compile(r"(\d{1,2}(?:\.\d+)?)\s*(?:°|deg\b|degrees?\b)")


def _named(s: Shape, words: tuple[str, ...]) -> bool:
    text = f"{s.id} {s.label} {s.part} {s.component}".lower()
    return any(w in text for w in words)


def _union(shapes: list[Shape]):
    out = shapes[0].manifold
    for s in shapes[1:]:
        out = out + s.manifold
    return out


def roof(b: Build) -> list[Issue]:
    """For a building: does the roof cover the walls, sit on them, and have the shape and pitch the plan asks for?
    Heights come from slicing the roof with thin vertical slabs at the middle and near both ends of each side."""
    from .drawing import is_building
    solid = [s for s in b.shapes if _solid(s)]
    roofs = [s for s in solid if _named(s, ROOF_WORDS)]
    if not roofs:
        return []
    lo, hi = _boxes(solid)
    if not is_building(lo.min(0), hi.max(0), b.program.get("units", "mm")):
        return []
    walls = [s for s in solid if _named(s, ("wall",)) and s not in roofs] or [s for s in solid if s not in roofs]
    wlo, whi = _boxes(walls)
    wlo, whi = wlo.min(0), whi.max(0)
    top = float(whi[1])
    shell = _union(roofs)
    rlo, rhi = _boxes(roofs)
    span_lo, span_hi = np.minimum(rlo.min(0), wlo) - 1.0, np.maximum(rhi.max(0), whi) + 1.0
    from manifold3d import Manifold

    def heights(axis: int, at: float) -> tuple[float, float] | None:
        """(lowest, highest) roof y on a vertical slab across the building at `axis` = `at`, or None if bare. The slab
        stays inside the walls on the other side, so eaves hanging past the walls do not count as dipping."""
        inset = (whi - wlo) * 0.03
        lo_, hi_ = np.maximum(span_lo, wlo + inset), np.minimum(span_hi, whi - inset)
        lo_[1], hi_[1] = span_lo[1], span_hi[1]
        size, centre = hi_ - lo_, (hi_ + lo_) / 2
        size[axis] = max((whi[axis] - wlo[axis]) * 0.01, 1e-3)
        centre[axis] = at
        bb = (shell ^ Manifold.cube(size.tolist(), True).translate(centre.tolist())).bounding_box()
        return None if not np.all(np.isfinite(bb)) or bb[4] < bb[1] else (float(bb[1]), float(bb[4]))

    roof_text = " ".join(f"{s.label} {s.part}" for s in roofs)
    bp = b.program.get("blueprint") or {}
    for part in bp.get("parts") or []:
        if isinstance(part, dict) and "roof" in str(part.get("name", "")).lower():
            roof_text += f" {part.get('name', '')} {part.get('role', '')} {part.get('shape', '')}"
    intent = (roof_text + " " + str(bp.get("summary", ""))).lower()
    wants_pitch = bool(PITCHED.search(intent)) and not BUTTERFLY.search(intent)
    out: list[Issue] = []
    label = roofs[0].label or "The roof"
    profile, lows = {}, []
    for axis in (0, 2):
        w = float(whi[axis] - wlo[axis])
        mid = float((whi[axis] + wlo[axis]) / 2)
        samples = {"middle": mid, "one end": float(wlo[axis]) + 0.06 * w, "the other end": float(whi[axis]) - 0.06 * w}
        h = {k: heights(axis, v) for k, v in samples.items()}
        bare = [k for k, v in h.items() if v is None]
        if bare:
            out.append(Issue("roof", "fix", roofs[0].component, f"{label} leaves the walls uncovered along "
                             f"{'XYZ'[axis]} ({', '.join(bare)}): the roof spans {rlo.min(0)[axis]:.0f} to "
                             f"{rhi.max(0)[axis]:.0f} but the walls run {wlo[axis]:.0f} to {whi[axis]:.0f}."))
            continue
        lows.append(min(v[0] for v in h.values()))
        profile[axis] = (h["middle"][1], max(h["one end"][1], h["the other end"][1]),
                         min(h["one end"][1], h["the other end"][1]), 0.44 * w)
    if out or len(profile) < 2:
        return out
    rises = {a: (mid - edge_hi) / run for a, (mid, edge_hi, _, run) in profile.items()}
    valleys = {a: (edge_lo - mid) / run for a, (mid, _, edge_lo, run) in profile.items()}
    ridge = max(rises, key=rises.get)
    if wants_pitch and any(v > 0.05 for v in valleys.values()):
        a = max(valleys, key=valleys.get)
        return [Issue("roof", "fix", roofs[0].component, f"{label} is low in the middle and high at the eaves along "
                      f"{'XYZ'[a]} (a V), but the plan asks for a pitched roof: each slope must rise toward the "
                      "ridge, so flip the panel's tilt.")]
    low = min(lows)
    if low < top - 0.08 * (top - float(wlo[1])):     # after the shape test: "a V, flip it" says more than "too low"
        return [Issue("roof", "fix", roofs[0].component, f"{label} dips to {low:.0f}, below the wall tops at "
                      f"{top:.0f}: it cuts down into the rooms.")]
    if wants_pitch and rises[ridge] < 0.05:
        return [Issue("roof", "fix", roofs[0].component, f"{label} is flat, but the plan asks for a pitched roof.")]
    stated = ANGLE.search(intent)
    if wants_pitch and stated:
        pitch = float(np.degrees(np.arctan(rises[ridge])))
        if abs(pitch - float(stated.group(1))) > 10:
            out.append(Issue("roof", "warn", roofs[0].component, f"{label} pitches at about {pitch:.0f} degrees "
                             f"across {'XYZ'[ridge]}; the plan says {stated.group(1)}."))
    return out


def _words(s: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z]+", s.lower()):
        if len(w) >= 3 and w not in STOP:
            out.append((w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)[:6])
    return out


def missing(b: Build) -> list[Issue]:
    """A listed part counts as built when its head noun, or at least half of its words, appears in a part name."""
    parts = (b.program.get("blueprint") or {}).get("parts") or []
    have = set(_words(" ".join([c.label for c in b.comps] + [o.get("label", "") for o in b.program["ops"]])))
    out = []
    for p in parts:
        name = str(p.get("name", "")) if isinstance(p, dict) else ""
        words = _words(name)
        if not words:
            continue
        hit = [w in have for w in words]
        if not (hit[-1] and sum(hit) * 2 >= len(words)):
            out.append(Issue("missing", "warn", "", f"The blueprint lists {name}, but no part is named for it."))
    return out


def stability(b: Build) -> list[Issue]:
    m = properties(b.program, [s for s in b.shapes if _solid(s)])
    if m.stands is False:
        return [Issue("tips", "fix", "", f"It would tip over: the centre of gravity ({m.kg:.1f} kg at "
                      f"x {m.cg[0]:.0f}, z {m.cg[2]:.0f}) lies outside the footprint on the floor. Widen the base, "
                      "move mass over it, or add a stand.")]
    return []


CHECKS = (floating, cavity_floating, overlaps, array_copies, thin_wall, off_axis, size, missing, stability, roof)


def critique(program: dict, shapes: list[Shape], comps: list[Component]) -> list[Issue]:
    if not shapes or not comps:
        return []
    b = Build(program, shapes, comps)
    return [i for check in CHECKS for i in check(b)]


def blocking(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "fix"]
