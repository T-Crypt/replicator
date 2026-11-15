"""Blueprint sheets: a dimensioned, third-angle technical drawing of a build, as SVG.

Views are vector projections of the real geometry. Each part's silhouette is filled with the paper colour and drawn
far to near, so nearer parts hide what lies behind them; crease edges a viewer could see add the detail. One section
view cuts the build: a floor plan 1.2 m up for anything building-sized, otherwise a cut through the centre so
interiors (a nozzle bell, a casing wall) show. Dimensions are measured; callouts number the parts list, whose masses
come from `physics`. No Qt here: the caller turns the SVG into pixels.
"""
from __future__ import annotations

import datetime
import math
from dataclasses import dataclass, field

import numpy as np
import shapely
import trimesh
from manifold3d import Manifold

from .assembly import Component
from .evaluate import RawMesh, Shape
from .physics import is_effect, properties

SHEET = (420.0, 297.0)                    # A3 landscape, millimetres
MARGIN = 10.0
TABLE_W = 112.0
SCALES = (10, 5, 2, 1, 1 / 2, 1 / 2.5, 1 / 4, 1 / 5, 1 / 10, 1 / 15, 1 / 20, 1 / 25, 1 / 30, 1 / 40, 1 / 50,
          1 / 75, 1 / 100, 1 / 150, 1 / 200, 1 / 250, 1 / 500, 1 / 1000)
CREASE_DEG = 32.0
PLAN_HEIGHT = 1200.0                      # mm above the floor: where architects cut a floor plan
FONT = "Inter, 'DejaVu Sans', 'Liberation Sans', Arial, Helvetica, sans-serif"   # plain sans, ISO 3098 in spirit
STYLES = {
    "blueprint": {"paper": "#143a6e", "ink": "#eaf2ff", "faint": "#9fb8dc", "cut": "#eaf2ff", "grid": "#1d4a86"},
    "paper": {"paper": "#ffffff", "ink": "#101418", "faint": "#6b7480", "cut": "#101418", "grid": "#e8ecf1"},
}

# view -> (2D axes as (index, sign) pairs, depth axis index, depth sign toward the viewer)
VIEWS = {
    "front": (((0, 1), (1, 1)), 2, 1),
    "top": (((0, 1), (2, -1)), 1, 1),
    "right": (((2, -1), (1, 1)), 0, 1),
}


@dataclass
class Part:
    shape_id: str
    component: str
    V: np.ndarray
    F: np.ndarray
    cut: np.ndarray | None = None         # faces lying on the section plane


@dataclass
class ViewArt:
    name: str
    title: str
    layers: list[tuple[shapely.Geometry, list[np.ndarray], shapely.Geometry | None, str]] = field(default_factory=list)
    lo: np.ndarray = field(default_factory=lambda: np.zeros(2))
    hi: np.ndarray = field(default_factory=lambda: np.zeros(2))
    anchors: dict[str, np.ndarray] = field(default_factory=dict)


def _xy(P: np.ndarray, view: str) -> np.ndarray:
    (a, sa), (b, sb) = VIEWS[view][0]
    return np.column_stack([P[..., a] * sa, P[..., b] * sb]) if P.ndim == 2 else \
        np.stack([P[..., a] * sa, P[..., b] * sb], -1)


def _toward(view: str) -> np.ndarray:
    d = np.zeros(3)
    d[VIEWS[view][1]] = VIEWS[view][2]
    return d


def _creases(V: np.ndarray, F: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Edges sharper than CREASE_DEG with at least one face turned to the viewer, as [k, 2, 3]."""
    m = trimesh.Trimesh(V, F, process=False)
    m.merge_vertices()
    if len(m.face_adjacency) == 0:
        return np.zeros((0, 2, 3))
    sharp = m.face_adjacency_angles > math.radians(CREASE_DEG)
    facing = (m.face_normals @ d) > 1e-6
    seen = facing[m.face_adjacency[:, 0]] | facing[m.face_adjacency[:, 1]]
    return m.vertices[m.face_adjacency_edges[sharp & seen]]


def _silhouette(V: np.ndarray, F: np.ndarray, view: str) -> shapely.Geometry:
    d = _toward(view)
    a, b, c = (V[F[:, i]] for i in range(3))
    keep = (np.cross(b - a, c - a) @ d) > 1e-9
    if not keep.any():
        return shapely.Polygon()
    tri = np.stack([_xy(a[keep], view), _xy(b[keep], view), _xy(c[keep], view)], 1)
    return shapely.union_all(shapely.polygons(tri)).buffer(0)


def view_art(parts: list[Part], view: str, title: str) -> ViewArt:
    art = ViewArt(view, title)
    axis, sign = VIEWS[view][1], VIEWS[view][2]
    order = sorted(parts, key=lambda p: float((p.V[:, axis] * sign).max()))      # far to near
    pts = []
    for p in order:
        sil = _silhouette(p.V, p.F, view)
        if sil.is_empty:
            continue
        lines = [_xy(e, view) for e in _creases(p.V, p.F, _toward(view))]
        cut = None
        if p.cut is not None and len(p.cut):
            cut = shapely.union_all(shapely.polygons(np.stack([_xy(p.cut[:, i], view) for i in range(3)], 1)))
        art.layers.append((sil, lines, cut, p.component))
        pts.append(np.asarray(sil.bounds).reshape(2, 2))
        c = np.asarray(sil.representative_point().coords[0])
        art.anchors.setdefault(p.component, c)
    if pts:
        allp = np.vstack(pts)
        art.lo, art.hi = allp.min(0), allp.max(0)
    return art


def _parts(shapes: list[Shape], trim: tuple[tuple[float, float, float], float] | None = None) -> list[Part]:
    out = []
    for s in shapes:
        m = s.manifold
        cut = None
        if trim is not None:
            if isinstance(m, RawMesh):
                continue
            m = m.trim_by_plane(trim[0], trim[1])
            if m.is_empty():
                continue
        mesh = m.to_mesh()
        V = np.asarray(mesh.vert_properties[:, :3], np.float64)
        F = np.asarray(mesh.tri_verts, np.int64)
        if trim is not None:
            n = -np.asarray(trim[0], float)
            a, b, c = (V[F[:, i]] for i in range(3))
            fn = np.cross(b - a, c - a)
            fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
            on = (fn @ n > 0.999) & (np.abs(a @ n + trim[1]) < 1e-3 * (1 + abs(trim[1])))
            cut = np.stack([a[on], b[on], c[on]], 1) if on.any() else None
        out.append(Part(s.id, s.component, V, F, cut))
    return out


def is_building(lo: np.ndarray, hi: np.ndarray, units: str) -> bool:
    size = (hi - lo) * {"mm": 1.0, "cm": 10.0, "m": 1000.0}.get(units, 1.0)
    return size[1] >= 2000 and max(size[0], size[2]) >= 3000


# ------------------------------------------------------------------------------------------------ SVG
def _f(v: float) -> str:
    return f"{v:.2f}".rstrip("0").rstrip(".")


def _path(g: shapely.Geometry, tf) -> str:
    polys = [g] if g.geom_type == "Polygon" else [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    out = []
    for poly in polys:
        for ring in [poly.exterior, *poly.interiors]:
            xy = tf(np.asarray(ring.coords))
            out.append("M" + "L".join(f"{_f(x)} {_f(y)}" for x, y in xy) + "Z")
    return "".join(out)


def _text(x, y, s, size=2.6, anchor="start", fill="", weight="normal", extra=""):
    s = str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (f'<text x="{_f(x)}" y="{_f(y)}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" '
            f'fill="{fill}" {extra}>{s}</text>')


def _dim(x1, y1, x2, y2, off, label, ink, horizontal=True):
    """A dimension line offset from the measured edge, with extension lines, arrows and the value."""
    a = 1.6
    if horizontal:
        y = y1 + off
        return (f'<path d="M{_f(x1)} {_f(y1)}V{_f(y + math.copysign(1.2, off))}M{_f(x2)} {_f(y2)}'
                f'V{_f(y + math.copysign(1.2, off))}" stroke="{ink}" stroke-width="0.13"/>'
                f'<path d="M{_f(x1)} {_f(y)}H{_f(x2)}" stroke="{ink}" stroke-width="0.18"/>'
                f'<path d="M{_f(x1)} {_f(y)}l{a} {-a / 3}v{2 * a / 3}zM{_f(x2)} {_f(y)}l{-a} {-a / 3}v{2 * a / 3}z" '
                f'fill="{ink}"/>' + _text((x1 + x2) / 2, y - 1, label, 2.5, "middle", ink))
    x = x1 + off
    return (f'<path d="M{_f(x1)} {_f(y1)}H{_f(x + math.copysign(1.2, off))}M{_f(x2)} {_f(y2)}'
            f'H{_f(x + math.copysign(1.2, off))}" stroke="{ink}" stroke-width="0.13"/>'
            f'<path d="M{_f(x)} {_f(y1)}V{_f(y2)}" stroke="{ink}" stroke-width="0.18"/>'
            f'<path d="M{_f(x)} {_f(y1)}l{-a / 3} {-a}h{2 * a / 3}zM{_f(x)} {_f(y2)}l{-a / 3} {a}h{2 * a / 3}z" '
            f'fill="{ink}"/>' + _text(x - 1, (y1 + y2) / 2, label, 2.5, "middle", ink,
                                      extra=f'transform="rotate(-90 {_f(x - 1)} {_f((y1 + y2) / 2)})"'))


def _scale_label(s: float) -> str:
    return f"{int(round(s))}:1" if s >= 1 else f"1:{int(round(1 / s))}"


def views_of(shapes: list[Shape], units: str) -> tuple[dict[str, ViewArt], np.ndarray, bool]:
    """The views a drawing shows, in model units: top, front and right, plus a section A-A through the middle for an
    object, or a floor plan cut at PLAN_HEIGHT in place of the top view for a building. Returns (views, size, building).
    The sheet and the DXF both draw from this, so they always show the same views."""
    solids = [s for s in shapes if not s.manifold.is_empty()]
    if not solids:
        raise ValueError("nothing to draw: the build has no visible parts")
    lo = np.min([s.manifold.bounding_box()[:3] for s in solids], axis=0)
    hi = np.max([s.manifold.bounding_box()[3:] for s in solids], axis=0)
    size = hi - lo
    building = is_building(lo, hi, units)
    parts = _parts(solids)
    if building:
        h = lo[1] + min(PLAN_HEIGHT / {"mm": 1.0, "cm": 10.0, "m": 1000.0}.get(units, 1.0), 0.5 * size[1])
        plan = view_art(_parts(solids, ((0.0, -1.0, 0.0), -h)), "top", f"PLAN  (CUT AT {h - lo[1]:.0f} {units})")
        views = {"top": plan, "front": view_art(parts, "front", "FRONT ELEVATION"),
                 "right": view_art(parts, "right", "RIGHT ELEVATION")}
    else:
        zc = (lo[2] + hi[2]) / 2
        views = {"top": view_art(parts, "top", "TOP"), "front": view_art(parts, "front", "FRONT"),
                 "right": view_art(parts, "right", "RIGHT"),
                 "section": view_art(_parts(solids, ((0.0, 0.0, -1.0), -zc)), "front", "SECTION A-A")}
    return views, size, building


def sheet_svg(program: dict, shapes: list[Shape], comps: list[Component], style: str = "blueprint",
              source: str = "Replicator") -> str:
    st = STYLES.get(style, STYLES["blueprint"])
    units = program.get("units", "mm")
    views, size, building = views_of(shapes, units)
    W, H, D = size[0], size[1], size[2]
    s, slots = _layout(W, H, D, "section" in views)

    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{SHEET[0]}mm" height="{SHEET[1]}mm" '
           f'viewBox="0 0 {SHEET[0]} {SHEET[1]}" font-family="{FONT}">',
           f'<rect width="{SHEET[0]}" height="{SHEET[1]}" fill="{st["paper"]}"/>']
    for gx in np.arange(0, SHEET[0], 10):
        out.append(f'<path d="M{_f(gx)} 0V{SHEET[1]}" stroke="{st["grid"]}" stroke-width="0.12"/>')
    for gy in np.arange(0, SHEET[1], 10):
        out.append(f'<path d="M0 {_f(gy)}H{SHEET[0]}" stroke="{st["grid"]}" stroke-width="0.12"/>')
    out.append(f'<rect x="{MARGIN}" y="{MARGIN}" width="{SHEET[0] - 2 * MARGIN}" height="{SHEET[1] - 2 * MARGIN}" '
               f'fill="none" stroke="{st["ink"]}" stroke-width="0.6"/>')

    number = {c.id: i + 1 for i, c in enumerate(comps)}
    for key, art in views.items():
        if art.hi[0] <= art.lo[0]:
            continue
        ox, oy = slots[key]

        def tf(xy, ox=ox, oy=oy, art=art):
            return np.column_stack([ox + (xy[:, 0] - art.lo[0]) * s, oy + (art.hi[1] - xy[:, 1]) * s])

        for sil, lines, cut, _ in art.layers:
            out.append(f'<path d="{_path(sil, tf)}" fill="{st["paper"]}" fill-rule="evenodd" stroke="{st["ink"]}" '
                       f'stroke-width="0.35" stroke-linejoin="round"/>')
            if lines:
                d = "".join(f"M{_f(a[0])} {_f(a[1])}L{_f(b[0])} {_f(b[1])}" for a, b in
                            (tf(np.asarray(seg)) for seg in lines))
                out.append(f'<path d="{d}" stroke="{st["ink"]}" stroke-width="0.16" opacity="0.85"/>')
            if cut is not None and not cut.is_empty:
                out.append(f'<path d="{_path(cut, tf)}" fill="{st["cut"]}" fill-opacity="0.55" fill-rule="evenodd" '
                           f'stroke="{st["ink"]}" stroke-width="0.45"/>')
        w, h = (art.hi - art.lo) * s
        out.append(_text(ox + w / 2, oy + h + 9, art.title, 3.0, "middle", st["ink"], "bold"))
        if key == "front":
            out.append(_dim(ox, oy + h, ox + w, oy + h, 5, f"{W:.0f}", st["ink"]))
            out.append(_dim(ox, oy, ox, oy + h, -5, f"{H:.0f}", st["ink"], horizontal=False))
        if key == "right":
            out.append(_dim(ox, oy + h, ox + w, oy + h, 5, f"{D:.0f}", st["ink"]))
        if key == "top" and building:
            out.append(_dim(ox, oy, ox + w, oy, -5, f"{W:.0f}", st["ink"]))
            out.append(_dim(ox, oy, ox, oy + h, -5, f"{D:.0f}", st["ink"], horizontal=False))
        if key == ("top" if building else "front"):
            out += _balloons(art, tf, number, ox, ox + w, oy, h, st)

    out += _table(program, shapes, comps, number, s, units, st, source, building)
    out.append("</svg>")
    return "\n".join(out)


def _layout(W: float, H: float, D: float, has_section: bool) -> tuple[float, dict[str, tuple[float, float]]]:
    """The largest standard scale at which the views fit, trying a single row under the top view (third angle) and
    a two-by-two grid with the section beside the top view. Returns (scale, view -> top-left corner in sheet mm)."""
    area_w = SHEET[0] - 2 * MARGIN - TABLE_W - 18 - 2 * 18
    area_h = SHEET[1] - 2 * MARGIN - 2 * 12
    gap = 16.0
    sec = W if has_section else 0.0
    plans = {
        "row": (W + D + sec, D + H, 2 if has_section else 1, 1),
        "grid": (max(W + sec, W + D), max(D, H if has_section else D) + H, 1, 1),
    }
    best = (0.0, "row")
    for name, (w, h, gx, gy) in plans.items():
        k = next((k for k in SCALES if w * k + gap * gx <= area_w and h * k + gap * gy <= area_h), SCALES[-1])
        if k > best[0]:
            best = (k, name)
    k, name = best
    x0, y0 = MARGIN + 30, MARGIN + 12
    if name == "row":
        fy = y0 + D * k + gap
        slots = {"top": (x0, y0), "front": (x0, fy), "right": (x0 + W * k + gap, fy)}
        if has_section:
            slots["section"] = (x0 + (W + D) * k + 2 * gap, fy)
    else:
        r1 = max(D, H if has_section else D) * k
        fy = y0 + r1 + gap
        slots = {"top": (x0, y0 + r1 - D * k), "front": (x0, fy), "right": (x0 + W * k + gap, fy)}
        if has_section:
            slots["section"] = (x0 + W * k + gap, y0 + r1 - H * k)
    return k, slots


def _balloons(art: ViewArt, tf, number: dict[str, int], left: float, right: float, top: float, h: float,
              st: dict) -> list[str]:
    """Numbered callouts in two columns beside the view, each sorted top to bottom so leaders don't cross."""
    pts = [(tf(c[None])[0], cid) for cid, c in art.anchors.items() if cid in number]
    mid = (left + right) / 2
    out = []
    for on_left, x in ((True, left - 16), (False, right + 9)):
        items = sorted((p for p in pts if (p[0][0] < mid) == on_left), key=lambda t: t[0][1])
        step = max(h / max(len(items), 1), 6.0)
        for k, (p, cid) in enumerate(items):
            y = top + step * (k + 0.5)
            end = x + (2.4 if on_left else -2.4)
            out.append(f'<path d="M{_f(p[0])} {_f(p[1])}L{_f(end)} {_f(y)}" stroke="{st["faint"]}" '
                       f'stroke-width="0.15"/><circle cx="{_f(p[0])}" cy="{_f(p[1])}" r="0.5" fill="{st["ink"]}"/>'
                       f'<circle cx="{_f(x)}" cy="{_f(y)}" r="2.4" fill="{st["paper"]}" stroke="{st["ink"]}" '
                       f'stroke-width="0.25"/>' + _text(x, y + 0.9, number[cid], 2.4, "middle", st["ink"], "bold"))
    return out


def _material_cell(names: list[str]) -> str:
    """One parts-list cell: the component's substance, 'mixed' for several, 'light effect' when it is only light."""
    real = sorted({n for n in names if n and not is_effect(n)})
    if not real:
        return "light effect" if any(is_effect(n) for n in names) else "-"
    return real[0].replace("_", " ") if len(real) == 1 else "mixed"


def _table(program, shapes, comps, number, s, units, st, source, building) -> list[str]:
    ink, faint = st["ink"], st["faint"]
    x = SHEET[0] - MARGIN - TABLE_W
    m = properties(program, [sh for sh in shapes if not isinstance(sh.manifold, RawMesh)])
    mats: dict[str, list[str]] = {}
    for sh in shapes:
        mats.setdefault(sh.component, []).append(sh.material or "")
    counts: dict[str, int] = {}
    for sh in shapes:
        counts[sh.component] = counts.get(sh.component, 0) + 1
    out = [f'<path d="M{_f(x)} {MARGIN}V{SHEET[1] - MARGIN}" stroke="{ink}" stroke-width="0.4"/>']
    y = MARGIN + 7
    out.append(_text(x + 3, y, "PARTS LIST", 3.0, fill=ink, weight="bold"))
    y += 5
    cols = (3, 10, 57, 90, 100)
    for cx, head in zip(cols, ("NO", "PART", "MATERIAL", "QTY", "kg")):
        out.append(_text(x + cx, y, head, 2.2, fill=faint, weight="bold"))
    rows = [c for c in comps if c.id in number][:30]
    for c in rows:
        y += 4.6
        mat = _material_cell(mats.get(c.id, []))
        out.append(f'<path d="M{_f(x)} {_f(y - 3.3)}H{_f(x + TABLE_W)}" stroke="{st["grid"]}" stroke-width="0.15"/>')
        out.append(_text(x + 3, y, number[c.id], 2.4, fill=ink, weight="bold"))
        out.append(_text(x + 10, y, c.label[:24], 2.3, fill=ink))
        out.append(_text(x + 57, y, mat[:16], 2.1, fill=faint))
        out.append(_text(x + 90, y, counts.get(c.id, 1), 2.3, fill=ink))
        kg = m.by_component.get(c.id)
        out.append(_text(x + 109, y, f"{kg:.1f}" if kg is not None else "-", 2.3, "end", ink))
    if len(comps) > len(rows):
        y += 4.6
        out.append(_text(x + 3, y, f"+ {len(comps) - len(rows)} more", 2.2, fill=faint))

    tb = SHEET[1] - MARGIN - 46
    out.append(f'<path d="M{_f(x)} {_f(tb)}H{SHEET[0] - MARGIN}" stroke="{ink}" stroke-width="0.4"/>')
    title = (program.get("blueprint") or {}).get("title") or program.get("name", "Untitled build")
    out.append(_text(x + 3, tb + 8, title[:38], 3.6, fill=ink, weight="bold"))
    size = " x ".join(f"{v:.0f}" for v in _extent(shapes))
    rows = [("SCALE", _scale_label(s)), ("UNITS", units), ("SIZE", f"{size} {units}"),
            ("MASS", f"{m.kg:,.1f} kg{' *' if m.assumed else ''}"),
            ("VIEWS", "THIRD ANGLE" + (", PLAN" if building else ", SECTION A-A")),
            ("SHEET", "A3"), ("DATE", datetime.date.today().isoformat()), ("SOURCE", source)]
    for k, (label, val) in enumerate(rows):
        yy = tb + 14 + (k % 4) * 6.5
        xx = x + 3 + (k // 4) * 54
        out.append(_text(xx, yy, label, 2.0, fill=faint, weight="bold"))
        out.append(_text(xx + 13, yy, str(val)[:26], 2.3, fill=ink))
    if m.assumed:
        out.append(_text(x + 3, SHEET[1] - MARGIN - 2, "* some densities assumed (no recognised material)", 1.9,
                         fill=faint))
    return out


def _extent(shapes: list[Shape]) -> np.ndarray:
    lo = np.min([s.manifold.bounding_box()[:3] for s in shapes], axis=0)
    hi = np.max([s.manifold.bounding_box()[3:] for s in shapes], axis=0)
    return hi - lo
