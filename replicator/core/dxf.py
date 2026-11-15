"""DXF out: the drawing's views at full size, in model units, for CAD, laser cutting and CNC.

The views come from drawing.views_of, the same function the A3 sheet uses: top (or a floor plan for a building),
front, right, and a section A-A for an object. They are laid out third angle in model space at 1:1, so a line
measured in LibreCAD or FreeCAD is the length the kernel built, not a length on paper.

The file is plain ASCII DXF R12 (AC1009) with LINE and TEXT entities only, the subset every reader takes. Layers:
  OUTLINE   silhouettes of each part (visible outline, front to back as drawn on the sheet)
  EDGES     creases: edges sharper than drawing.CREASE_DEG facing the viewer
  SECTION   outline of material cut by the section or plan plane
  DIMS      overall sizes, as extension and dimension lines with their figure
  TEXT      view titles
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import shapely

from . import drawing
from .evaluate import Shape

__all__ = ["LAYERS", "entities", "write"]

LAYERS = {"OUTLINE": 7, "EDGES": 8, "SECTION": 1, "DIMS": 3, "TEXT": 5}    # ACI colours


def _rings(g: shapely.Geometry):
    polys = [g] if g.geom_type == "Polygon" else [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    for poly in polys:
        for ring in [poly.exterior, *poly.interiors]:
            yield np.asarray(ring.coords)


def _placement(views: dict, size: np.ndarray) -> dict[str, np.ndarray]:
    """Lower-left corner of each view in model space: front at the origin, top above it, right beside it, the
    section beside the right view (third angle). Gaps scale with the object so a house and a bolt both read."""
    W, H, D = size
    gap = 0.25 * float(max(size))
    out = {"front": np.array([0.0, 0.0]), "top": np.array([0.0, H + gap]), "right": np.array([W + gap, 0.0])}
    if "section" in views:
        out["section"] = np.array([W + D + 2 * gap, 0.0])
    return out


def entities(shapes: list[Shape], units: str = "mm") -> list[tuple]:
    """Every entity as ("LINE", layer, x1, y1, x2, y2) or ("TEXT", layer, x, y, height, text), in model units."""
    views, size, _ = drawing.views_of(shapes, units)
    where = _placement(views, size)
    W, H, D = (float(v) for v in size)
    text_h = 0.03 * float(max(size))
    out: list[tuple] = []

    def lines(xy: np.ndarray, layer: str, o: np.ndarray, lo: np.ndarray):
        p = xy - lo + o
        for a, b in zip(p[:-1], p[1:]):
            if np.any(a != b):
                out.append(("LINE", layer, *a, *b))

    for key, art in views.items():
        if art.hi[0] <= art.lo[0]:
            continue
        o, lo = where[key], art.lo
        for sil, creases, cut, _ in art.layers:
            for ring in _rings(sil):
                lines(ring, "OUTLINE", o, lo)
            for seg in creases:
                lines(np.asarray(seg), "EDGES", o, lo)
            if cut is not None and not cut.is_empty:
                for ring in _rings(cut):
                    lines(ring, "SECTION", o, lo)
        out.append(("TEXT", "TEXT", float(o[0]), float(o[1] - 2.2 * text_h), text_h, art.title))

    def dim(x1, y1, x2, y2, off, label, horizontal=True):
        if horizontal:
            y = y1 + off
            out.extend([("LINE", "DIMS", x1, y1, x1, y), ("LINE", "DIMS", x2, y2, x2, y), ("LINE", "DIMS", x1, y, x2, y),
                        ("TEXT", "DIMS", (x1 + x2) / 2, y + 0.3 * text_h, text_h, label)])
        else:
            x = x1 + off
            out.extend([("LINE", "DIMS", x1, y1, x, y1), ("LINE", "DIMS", x2, y2, x, y2), ("LINE", "DIMS", x, y1, x, y2),
                        ("TEXT", "DIMS", x - 1.2 * text_h * len(label) * 0.6, (y1 + y2) / 2, text_h, label)])

    off = 1.5 * text_h
    f, r = where["front"], where["right"]
    dim(f[0], f[1] + H, f[0] + W, f[1] + H, off, f"{W:.0f}")
    dim(f[0], f[1], f[0], f[1] + H, -off, f"{H:.0f}", horizontal=False)
    dim(r[0], r[1] + H, r[0] + D, r[1] + H, off, f"{D:.0f}")
    return out


def _pairs(code: int, value) -> str:
    return f"{code}\n{value}\n"


def write(shapes: list[Shape], path: str | Path, units: str = "mm") -> Path:
    path = Path(path)
    ents = entities(shapes, units)
    xs = [v for e in ents if e[0] == "LINE" for v in (e[2], e[4])]
    ys = [v for e in ents if e[0] == "LINE" for v in (e[3], e[5])]
    out = [_pairs(0, "SECTION"), _pairs(2, "HEADER"), _pairs(9, "$ACADVER"), _pairs(1, "AC1009"),
           _pairs(9, "$EXTMIN"), _pairs(10, min(xs)), _pairs(20, min(ys)),
           _pairs(9, "$EXTMAX"), _pairs(10, max(xs)), _pairs(20, max(ys)), _pairs(0, "ENDSEC"),
           _pairs(0, "SECTION"), _pairs(2, "TABLES"), _pairs(0, "TABLE"), _pairs(2, "LAYER"), _pairs(70, len(LAYERS))]
    for name, colour in LAYERS.items():
        out += [_pairs(0, "LAYER"), _pairs(2, name), _pairs(70, 0), _pairs(62, colour), _pairs(6, "CONTINUOUS")]
    out += [_pairs(0, "ENDTAB"), _pairs(0, "ENDSEC"), _pairs(0, "SECTION"), _pairs(2, "ENTITIES")]
    for e in ents:
        if e[0] == "LINE":
            _, layer, x1, y1, x2, y2 = e
            out += [_pairs(0, "LINE"), _pairs(8, layer), _pairs(10, f"{x1:.6f}"), _pairs(20, f"{y1:.6f}"),
                    _pairs(30, "0.0"), _pairs(11, f"{x2:.6f}"), _pairs(21, f"{y2:.6f}"), _pairs(31, "0.0")]
        else:
            _, layer, x, y, h, text = e
            out += [_pairs(0, "TEXT"), _pairs(8, layer), _pairs(10, f"{x:.6f}"), _pairs(20, f"{y:.6f}"),
                    _pairs(30, "0.0"), _pairs(40, f"{h:.6f}"), _pairs(1, text.replace("\n", " "))]
    out += [_pairs(0, "ENDSEC"), _pairs(0, "EOF")]
    path.write_text("".join(out))
    return path
