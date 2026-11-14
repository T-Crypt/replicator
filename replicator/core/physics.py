"""Mass properties from the geometry: mass per part from its volume and a density chosen by material name, the centre
of gravity, and whether the object stands. Volumes are measured; densities are typical handbook values, so every mass
is `computed`, and a part whose material names no known substance falls back to aluminium and says so.
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
    ("glow", 1200), ("emissive", 1200), ("led", 1200),
)
FALLBACK = ("aluminium (assumed)", 2700)


def density(material: str | None) -> tuple[str, float, bool]:
    key = (material or "").lower()
    for name, rho in DENSITY:
        if name in key:
            return name, rho, True
    return FALLBACK[0], FALLBACK[1], False


@dataclass
class Mass:
    kg: float
    cg: list[float]
    by_component: dict[str, float]
    assumed: list[str]                    # shape ids whose density is a fallback
    stands: bool | None                   # None when it does not rest on the floor (levitating display pose)
    inertia: list[float] = field(default_factory=list)   # principal moments about the CG, kg m^2, ascending


def properties(program: dict, shapes: list[Shape]) -> Mass:
    s = UNIT_M.get(program.get("units", "mm"), 1e-3)
    total, moment, by_comp, assumed = 0.0, np.zeros(3), {}, []
    second = np.zeros((3, 3))             # sum of rho * integral of x x^T dV about the origin, kg mm^2
    for sh in shapes:
        _, rho, known = density(sh.material)
        if not known:
            assumed.append(sh.id)
        V, F = sh.arrays()
        a, b, c = (V[F[:, i]].astype(np.float64) for i in range(3))
        vol6 = np.einsum("ij,ij->i", a, np.cross(b, c))
        vol = abs(vol6.sum()) / 6.0
        if vol <= 0:
            continue
        centroid = ((a + b + c) * vol6[:, None]).sum(0) / (4.0 * vol6.sum())
        kg = vol * s ** 3 * rho
        sgn = 1.0 if vol6.sum() > 0 else -1.0
        S = a + b + c
        cov = (np.einsum("n,ni,nj->ij", vol6 * sgn, a, a) + np.einsum("n,ni,nj->ij", vol6 * sgn, b, b)
               + np.einsum("n,ni,nj->ij", vol6 * sgn, c, c) + np.einsum("n,ni,nj->ij", vol6 * sgn, S, S)) / 120.0
        second += cov * (kg / vol)
        total += kg
        moment += kg * centroid
        by_comp[sh.component] = by_comp.get(sh.component, 0.0) + kg
    cg = (moment / total) if total else np.zeros(3)
    return Mass(round(float(total), 3), [round(float(v), 1) for v in cg],
                {k: round(float(v), 3) for k, v in by_comp.items()},
                assumed, _stands(shapes, cg), _principal(second, total, cg, s))


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
