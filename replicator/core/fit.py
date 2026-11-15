"""Fitting a build onto a printer bed, in the print frame: Z up, millimetres (FR-PR-13, FR-PR-14).

A BuildProgram is Y-up in its own units; the print frame is the same turn the STL/3MF exporters apply
(core/export.py, Y_TO_Z_UP), so what fits here is exactly what the exported file claims. Nothing is
ever clipped: a build that does not fit is refused with the overflow per axis, and the fit functions
give the scale or orientation that would make it fit.

The six lay-flat orientations are axis-aligned permutations of the build's extent: as built (program Y
up), yaw 90, or standing on another face. best_orientation (orient to fit) weighs all six; scale_to_fit
keeps the replica upright - as built or yaw, never on its end - because a scaled copy of the program
(program.scale_program) can only be scaled, not rotated, and that is the factor a written file takes.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .evaluate import bounds

__all__ = ["Orientation", "Fit", "AXES", "extent", "orientations", "check",
           "best_orientation", "scale_to_fit", "replica_scale"]

UNIT_TO_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0}
AXES = ("X", "Y", "Z")


@dataclass(frozen=True)
class Orientation:
    """A way the build can lie flat on the bed: its name and the size it occupies in the print frame."""
    name: str
    size: tuple[float, float, float]


@dataclass(frozen=True)
class Fit:
    """One fit check, per axis in the print frame (mm): `size` what the build occupies at `scale` in
    `orientation`, `usable` the printer's volume after margins, then the slack (`clearance`) or the
    excess (`overflow`) each axis leaves or takes."""
    fits: bool
    scale: float
    orientation: str
    size: tuple[float, float, float]
    usable: tuple[float, float, float]
    clearance: tuple[float, float, float]
    overflow: tuple[float, float, float]


# The six lay-flat layouts, as permutations of the print-frame extent: which extent axis each print
# axis (x, y bed, z-up) takes. "As built" is the identity (the exporters' Y-to-Z turn already puts the
# build's up axis on print Z); the rest stand it on its other faces.
_LAYOUTS: tuple[tuple[str, tuple[int, int, int]], ...] = (
    ("as built", (0, 1, 2)),
    ("yaw 90", (1, 0, 2)),
    ("on its side (X up)", (1, 2, 0)),
    ("on its side (X up), yaw 90", (2, 1, 0)),
    ("on its side (Y up)", (0, 2, 1)),
    ("on its side (Y up), yaw 90", (2, 0, 1)),
)


def extent(shapes, units: str = "mm") -> np.ndarray:
    """The size of the whole build as assembled (x, y, z), in millimetres in the print frame."""
    if not shapes:
        raise ValueError("nothing to measure: the build has no visible parts")
    if units not in UNIT_TO_MM:
        raise ValueError(f"units must be one of {sorted(UNIT_TO_MM)}")
    lo, hi = bounds(shapes)
    s = np.array([hi[i] - lo[i] for i in range(3)], dtype=np.float64) * UNIT_TO_MM[units]
    return np.array([s[0], s[2], s[1]])


def orientations(shapes, units: str = "mm") -> tuple[Orientation, ...]:
    e = extent(shapes, units)
    return tuple(Orientation(name, tuple(float(e[i]) for i in perm)) for name, perm in _LAYOUTS)


def _by_name(orientations, name: str) -> Orientation:
    for o in orientations:
        if o.name == name:
            return o
    raise ValueError(f"unknown orientation {name!r}; one of {[o.name for o in orientations]}")


def check(shapes, units: str, printer, scale: float = 1.0, orientation: str = "as built") -> Fit:
    """Does the build, at `scale` and lying in `orientation`, stay inside the printer's usable volume?"""
    if not (isinstance(scale, (int, float)) and math.isfinite(scale) and scale > 0):
        raise ValueError("scale must be a positive number")
    o = _by_name(orientations(shapes, units), orientation)
    size = np.asarray(o.size, dtype=np.float64) * scale
    usable = np.asarray(printer.usable(), dtype=np.float64)
    overflow = np.maximum(0.0, size - usable)
    clearance = np.maximum(0.0, usable - size)
    return Fit(bool(overflow.max() == 0.0), float(scale), o.name,
               tuple(float(v) for v in size), tuple(float(v) for v in usable),
               tuple(float(v) for v in clearance), tuple(float(v) for v in overflow))


def best_orientation(shapes, units: str, printer) -> Fit:
    """At scale 1, the layout that fits with the most minimum clearance; if none fits, the one with
    the least total overflow."""
    fits = [check(shapes, units, printer, orientation=o.name) for o in orientations(shapes, units)]
    ok = [f for f in fits if f.fits]
    if ok:
        return max(ok, key=lambda f: min(f.clearance))
    return min(fits, key=lambda f: sum(f.overflow))


def scale_to_fit(shapes, units: str, printer, allow_rotate: bool = True, upscale: bool = False) -> Fit:
    """The largest uniform scale at which the build fits, staying upright: as built, plus a 90-degree
    yaw when `allow_rotate`. Standing the build on its side is left to best_orientation - a replica
    stands as it was built, and a scaled copy of the program (scale_program) cannot be rotated anyway.
    Capped at 1.0 unless `upscale`."""
    opts = orientations(shapes, units)
    if not allow_rotate:
        opts = opts[:1]
    else:
        opts = opts[:2]
    usable = np.asarray(printer.usable(), dtype=np.float64)
    best: tuple[float, Orientation] | None = None
    for o in opts:
        size = np.asarray(o.size, dtype=np.float64)
        with np.errstate(divide="ignore"):
            s = float(np.min(np.where(size > 0, usable / np.where(size > 0, size, 1.0), np.inf)))
        if not math.isfinite(s) or s <= 0:
            continue
        if not upscale:
            s = min(s, 1.0)
        if s < 1.0:
            s *= 1.0 - 1e-9        # usable/size is a floating-point knife edge: stand off the edge
        if best is None or s > best[0]:
            best = (s, o)
    if best is None:
        raise ValueError(f"{printer.name}: the build has no finite extent to fit")
    s, o = best
    f = check(shapes, units, printer, scale=s, orientation=o.name)
    if not f.fits:                  # unreachable: the knife-edge stand-off keeps check honest
        raise ValueError(f"{printer.name}: internal error, the fitted scale {s!r} still overflows")
    return f


def replica_scale(preset: str, shapes, units: str, printer) -> float:
    """The uniform factor for a replica print: "1:1" (full size), "1:<n>", "fit" (largest factor the
    as-built build takes on the bed), or "height:<mm>" (bring the print-frame height to that many
    millimetres). All of these are what a scaled copy of the program will actually occupy."""
    if preset == "1:1":
        return 1.0
    if preset == "fit":
        return scale_to_fit(shapes, units, printer, allow_rotate=False).scale
    if preset.startswith("1:"):
        try:
            n = float(preset[2:])
        except ValueError:
            raise ValueError(f"replica preset {preset!r} is 1:<n>, a number") from None
        if not (math.isfinite(n) and n >= 1):
            raise ValueError(f"replica {preset!r}: n must be >= 1")
        return 1.0 / n
    if preset.startswith("height:"):
        try:
            h = float(preset[len("height:"):])
        except ValueError:
            raise ValueError(f"replica preset {preset!r} is height:<mm>, a number") from None
        if not (math.isfinite(h) and h > 0):
            raise ValueError(f"replica {preset!r}: the target height must be positive millimetres")
        z = extent(shapes, units)[2]
        if z <= 0:
            raise ValueError("the build has no height to scale against")
        return h / z
    raise ValueError(f"unknown replica preset {preset!r}; use 1:1, 1:<n>, fit or height:<mm>")
