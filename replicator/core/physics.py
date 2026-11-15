"""Mass properties from the geometry: mass per part from its volume and a density chosen by material name, the centre
of gravity, and whether the object stands. Volumes are measured; densities are typical handbook values, so every mass
is `computed`, and a part whose material names no known substance falls back to aluminium and says so. A light effect
(a glow, emissive or holo material that names no substance) is not matter: it has no mass and is left out.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import ConvexHull

from .evaluate import Shape

UNIT_M = {"mm": 1e-3, "cm": 1e-2, "m": 1.0}
DENSITY = (                               # kg/m^3; first match in the material key or label wins
    ("gold", 19300), ("tungsten", 19250), ("lead", 11340), ("copper", 8960), ("brass", 8500), ("bronze", 8800),
    ("inconel", 8440), ("nickel", 8900), ("steel", 7850), ("iron", 7870), ("chrome", 7190), ("gunmetal", 8700),
    ("titanium", 4430), ("ceramic", 3900), ("alumin", 2700), ("anodis", 2700), ("clay", 1800), ("glass", 2500), ("concrete", 2400), ("stone", 2600),
    ("tps", 150), ("carbon", 1600), ("composite", 1800), ("kevlar", 1440), ("peek", 1300), ("rubber", 1150), ("tyre", 1150), ("tire", 1150), ("polymer", 1200),
    ("plastic", 1200), ("abs", 1050), ("pla", 1240), ("nylon", 1150), ("wood", 600), ("foam", 50),
    ("acetal", 1410), ("acrylic", 1180), ("pmma", 1180), ("petg", 1270), ("pcb", 1850), ("fr4", 1850), ("silicon", 2330),
    ("coolant", 1050), ("led", 1200),
)
FALLBACK = ("aluminium (assumed)", 2700)
EFFECTS = ("glow", "emissive", "holo")    # display light, not a substance, unless the name also names one


def density(material: str | None) -> tuple[str, float, bool]:
    key = (material or "").lower()
    for name, rho in DENSITY:
        if name in key:
            return name, rho, True
    if is_effect(material):
        return "effect", 0.0, True
    return FALLBACK[0], FALLBACK[1], False


def is_effect(material: str | None) -> bool:
    key = (material or "").lower()
    return any(e in key for e in EFFECTS) and not any(name in key for name, _ in DENSITY)


@dataclass
class Mass:
    kg: float
    cg: list[float]
    by_component: dict[str, float]
    assumed: list[str]                    # shape ids whose density is a fallback
    stands: bool | None                   # None when it does not rest on the floor (levitating display pose)
    inertia: list[float] = field(default_factory=list)   # principal moments about the CG, kg m^2, ascending


def _integrals(sh: Shape, unit: float) -> tuple[float, np.ndarray, np.ndarray] | None:
    """(kg, centroid in program units, rho * integral of x x^T dV about the origin in kg x unit^2) of one solid, or
    None when it has no mass (a light effect, or no volume)."""
    _, rho, _ = density(sh.material)
    if not rho:
        return None
    V, F = sh.arrays()
    a, b, c = (V[F[:, i]].astype(np.float64) for i in range(3))
    vol6 = np.einsum("ij,ij->i", a, np.cross(b, c))
    vol = abs(vol6.sum()) / 6.0
    if vol <= 0:
        return None
    centroid = ((a + b + c) * vol6[:, None]).sum(0) / (4.0 * vol6.sum())
    kg = vol * unit ** 3 * rho
    sgn = 1.0 if vol6.sum() > 0 else -1.0
    S = a + b + c
    cov = (np.einsum("n,ni,nj->ij", vol6 * sgn, a, a) + np.einsum("n,ni,nj->ij", vol6 * sgn, b, b)
           + np.einsum("n,ni,nj->ij", vol6 * sgn, c, c) + np.einsum("n,ni,nj->ij", vol6 * sgn, S, S)) / 120.0
    return kg, centroid, cov * (kg / vol)


def properties(program: dict, shapes: list[Shape]) -> Mass:
    s = UNIT_M.get(program.get("units", "mm"), 1e-3)
    total, moment, by_comp, assumed = 0.0, np.zeros(3), {}, []
    second = np.zeros((3, 3))
    for sh in shapes:
        if not density(sh.material)[2]:
            assumed.append(sh.id)
        got = _integrals(sh, s)
        if got is None:
            continue
        kg, centroid, sec = got
        second += sec
        total += kg
        moment += kg * centroid
        by_comp[sh.component] = by_comp.get(sh.component, 0.0) + kg
    cg = (moment / total) if total else np.zeros(3)
    return Mass(round(float(total), 3), [round(float(v), 1) for v in cg],
                {k: round(float(v), 3) for k, v in by_comp.items()},
                assumed, _stands(shapes, cg), _principal(second, total, cg, s))


@dataclass(frozen=True)
class Body:
    """Rigid-body properties of a group of solids, in SI: kg, the centre of mass in metres (program axes), and the
    inertia tensor about that centre in kg m^2 (program axes)."""
    kg: float
    com: tuple[float, float, float]
    inertia: tuple[tuple[float, float, float], ...]


def body(program: dict, shapes: list[Shape]) -> Body:
    s = UNIT_M.get(program.get("units", "mm"), 1e-3)
    total, moment, second = 0.0, np.zeros(3), np.zeros((3, 3))
    for sh in shapes:
        got = _integrals(sh, s)
        if got is None:
            continue
        kg, centroid, sec = got
        total += kg
        moment += kg * centroid
        second += sec
    if not total:
        return Body(0.0, (0.0, 0.0, 0.0), ((0.0,) * 3,) * 3)
    cg = moment / total
    cov = (second - total * np.outer(cg, cg)) * s ** 2
    tensor = np.trace(cov) * np.eye(3) - cov
    return Body(float(total), tuple(float(v) for v in cg * s), tuple(tuple(float(v) for v in row) for row in tensor))


def _principal(second: np.ndarray, total: float, cg: np.ndarray, unit: float) -> list[float]:
    if not total:
        return [0.0, 0.0, 0.0]
    cov = second - total * np.outer(cg, cg)
    inertia = (np.trace(cov) * np.eye(3) - cov) * (unit / 1e-3) ** 2 * 1e-6
    return [float(v) for v in np.linalg.eigvalsh(inertia)]


def _stands(shapes: list[Shape], cg: np.ndarray) -> bool | None:
    """True when the centre of gravity lies over the footprint on the floor (the convex hull of everything touching
    the lowest plane), False when it would tip, None when the footprint is a point or line (it would roll or lie)."""
    V = np.vstack([sh.arrays()[0] for sh in shapes]).astype(np.float64)
    lo, hi = V.min(0), V.max(0)
    foot = V[V[:, 1] <= lo[1] + 0.005 * max(hi[1] - lo[1], 1e-9)][:, [0, 2]]
    if len(foot) < 3:
        return None
    try:
        hull = ConvexHull(foot)
    except Exception:  # noqa: BLE001 - collinear contact: a line, not an area
        return None
    if hull.volume < 1e-4 * (hi[0] - lo[0]) * (hi[2] - lo[2]):
        return None
    eq = hull.equations
    return bool(np.all(eq[:, :2] @ np.array([cg[0], cg[2]]) + eq[:, 2] <= 1e-6))
