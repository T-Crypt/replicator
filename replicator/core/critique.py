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
from .evaluate import RawMesh, Shape
from .physics import properties

AXISYM = {"cylinder", "tube", "torus", "revolve", "nozzle", "rotor", "capsule", "gear", "helix"}
CLIP_SHARE = 0.25        # overlap, as a share of the smaller part, that reads as parts passing through each other
BURIED_SHARE = 0.95
SIZE_TOLERANCE = 0.35
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


def floating(b: Build) -> list[Issue]:
    if len(b.comps) < 2:
        return []
    tol = 0.01 * float(np.linalg.norm(b.size))
    out = []
    for c in b.comps:
        gaps = [(_gap(c.lo, c.hi, o.lo, o.hi), o) for o in b.comps if o is not c]
        gap, near = min(gaps, key=lambda t: t[0])
        if gap > tol:
            out.append(Issue("floating", "fix", c.id, f"{c.label} floats free: it touches no other part "
                             f"(nearest is {near.label}, {gap:.0f} {b.program.get('units', 'mm')} away). "
                             "Move it until it is attached."))
    return out


def _pairs(b: Build):
    solids = [s for s in b.shapes if _solid(s)]
    boxes = [_box(s) for s in solids]
    for i in range(len(solids)):
        for j in range(i + 1, len(solids)):
            if solids[i].component != solids[j].component and _gap(*boxes[i], *boxes[j]) == 0.0:
                yield solids[i], solids[j]


def overlaps(b: Build) -> list[Issue]:
    out, buried = [], set()
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
        elif CLIP_SHARE <= share < BURIED_SHARE:
            out.append(Issue("clipping", "warn", small.component, f"{small.label} passes through {big.label} "
                             f"({share:.0%} of it overlaps)."))
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
    off = [i for i in range(3) if abs(got[i] - want[i]) > SIZE_TOLERANCE * want[i]]
    if not off:
        return []
    fmt = lambda v: " x ".join(f"{x:.0f}" for x in v)  # noqa: E731
    return [Issue("size", "warn", "", f"Built {fmt(got)} but the blueprint plans {fmt(want)} "
                  f"(off on {', '.join('XYZ'[i] for i in off)}).")]


def _words(s: str) -> set[str]:
    return {w[:6] for w in re.findall(r"[a-z]+", s.lower()) if len(w) >= 3 and w not in STOP}


def missing(b: Build) -> list[Issue]:
    parts = (b.program.get("blueprint") or {}).get("parts") or []
    names = " ".join([c.label for c in b.comps] + [o.get("label", "") for o in b.program["ops"]])
    have = _words(names)
    out = []
    for p in parts:
        name = str(p.get("name", "")) if isinstance(p, dict) else ""
        if name and not (_words(name) & have):
            out.append(Issue("missing", "warn", "", f"The blueprint lists {name}, but no part is named for it."))
    return out


def stability(b: Build) -> list[Issue]:
    m = properties(b.program, [s for s in b.shapes if _solid(s)])
    if m.stands is False:
        return [Issue("tips", "fix", "", f"It would tip over: the centre of gravity ({m.kg:.1f} kg at "
                      f"x {m.cg[0]:.0f}, z {m.cg[2]:.0f}) lies outside the footprint on the floor. Widen the base, "
                      "move mass over it, or add a stand.")]
    return []


CHECKS = (floating, overlaps, off_axis, size, missing, stability)


def critique(program: dict, shapes: list[Shape], comps: list[Component]) -> list[Issue]:
    if not shapes or not comps:
        return []
    b = Build(program, shapes, comps)
    return [i for check in CHECKS for i in check(b)]


def blocking(issues: list[Issue]) -> list[Issue]:
    return [i for i in issues if i.severity == "fix"]
