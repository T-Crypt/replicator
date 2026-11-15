"""Assemblies and exploded views (Dissect).

Components are groups of leaf shapes (`component` on the op, inherited through inputs). The exploded layout is the
one engineering drawings use: components are packed along the assembly's main axis in build order with clearance
between neighbours, so nothing overlaps at full explosion; components that sit off the axis (side-mounted pumps,
pylons, fins) also move straight out radially. A second level spreads the parts inside each component.

Everything here is measured from the geometry (observed), never guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .evaluate import Shape

PALETTE = ["#2fb8ff", "#ff8a3d", "#7bd88f", "#c792ea", "#ffcb6b", "#f07178", "#89ddff", "#c3e88d",
           "#f78c6c", "#82aaff", "#ff5370", "#b2ccd6"]


@dataclass
class Component:
    id: str
    label: str
    role: str = ""
    color: str = "#2fb8ff"
    shapes: list[str] = field(default_factory=list)
    order: int = 0                       # first build step that touches it
    lo: np.ndarray | None = None
    hi: np.ndarray | None = None
    offset: np.ndarray | None = None     # component displacement at explode = 1

    @property
    def center(self) -> np.ndarray:
        return (self.lo + self.hi) / 2


def _bbox(s: Shape) -> tuple[np.ndarray, np.ndarray]:
    b = s.manifold.bounding_box()
    return np.array(b[:3]), np.array(b[3:])


ACRONYMS = {"cpu", "gpu", "psu", "pcb", "ram", "ssd", "usb", "hdmi", "io", "led", "fpv", "rf", "ac", "dc", "esc", "lox",
            "rcs", "imu", "gps", "mcu", "soc", "vrm", "fpc", "pcie", "mipi", "sd"}


def _title(cid: str) -> str:
    """A component id as a label: words capitalised, acronyms kept upright ("cpu_block" -> "CPU Block")."""
    return " ".join(w.upper() if w.lower() in ACRONYMS else w.capitalize() for w in cid.replace("_", " ").split())

def components(program: dict, shapes: list[Shape]) -> list[Component]:
    meta = {c["id"]: c for c in program.get("components", []) if isinstance(c, dict)}
    first_step = {}
    for i, op in enumerate(program["ops"]):
        cid = op.get("component")
        if cid and cid not in first_step:
            first_step[cid] = i
    out: dict[str, Component] = {}
    for s in shapes:
        c = out.get(s.component)
        lo, hi = _bbox(s)
        if c is None:
            m = meta.get(s.component, {})
            c = out[s.component] = Component(s.component, m.get("label") or _title(s.component),
                                             m.get("role", ""), shapes=[], order=first_step.get(s.component, 10 ** 6),
                                             lo=lo, hi=hi)
        else:
            c.lo, c.hi = np.minimum(c.lo, lo), np.maximum(c.hi, hi)
        c.shapes.append(s.id)
    comps = sorted(out.values(), key=lambda c: (c.order, c.id))
    for i, c in enumerate(comps):
        c.color = meta.get(c.id, {}).get("color") or PALETTE[i % len(PALETTE)]
    return comps


def explode(shapes: list[Shape], comps: list[Component], spread: float = 0.35) -> dict[str, list[float]]:
    """shape id -> [dx, dy, dz] at explode factor 1 (component offset plus a small in-component spread)."""
    if not shapes:
        return {}
    lo = np.min([c.lo for c in comps], axis=0)
    hi = np.max([c.hi for c in comps], axis=0)
    C = (lo + hi) / 2
    ext = hi - lo
    ax = int(np.argmax(ext))                         # main axis: the longest extent
    a = np.zeros(3)
    a[ax] = 1.0

    # 1) axial stagger: order components along the axis and spread them over ~1.6x the assembly length. Nested,
    #    coaxial parts (a liner inside a casing) telescope out instead of being packed end to end.
    order = sorted(comps, key=lambda c: (c.center[ax], c.order))
    n = len(order)
    step = min(max(ext[ax] * 1.6 / max(n - 1, 1), ext[ax] * 0.08), ext[ax] * 0.6)
    for rank, c in enumerate(order):
        c.offset = a * ((rank - (n - 1) / 2) * step)

    # 2) radial push for components that sit off the axis (side-mounted parts)
    radial_extent = max(np.delete(ext, ax).max(), 1e-6)
    for c in comps:
        r = c.center - C
        r[ax] = 0.0
        d = np.linalg.norm(r)
        if d > radial_extent * 0.12:
            c.offset = c.offset + r / d * radial_extent * 0.55

    # 3) inside a component, parts spread away from the component centre
    out: dict[str, list[float]] = {}
    by_id = {s.id: s for s in shapes}
    for c in comps:
        cc = c.center
        for sid in c.shapes:
            slo, shi = _bbox(by_id[sid])
            v = (slo + shi) / 2 - cc
            n = np.linalg.norm(v)
            inner = v / n * min(n, ext.max() * 0.25) * spread if n > 1e-6 and len(c.shapes) > 1 else np.zeros(3)
            out[sid] = (c.offset + inner).tolist()
    return out
