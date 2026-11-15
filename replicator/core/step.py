"""STEP (ISO 10303-21, AP214) out of exact Manifold solids, as faceted B-rep.

Every connected lump of a part becomes one MANIFOLD_SOLID_BREP (BREP_WITH_VOIDS when it encloses a cavity). Adjacent coplanar triangles merge into one planar face (a box is six faces,
not twelve triangles), with holes kept as inner bounds; edges and vertices are shared across faces, so a CAD reader
gets a closed shell, not a soup. Surfaces are planes: a cylinder arrives as a ring of flat faces, exactly the facets
Manifold built, so volumes and mass match the workshop to the last facet. Analytic surfaces need an OCCT layer.

Written Z-up in the program's units (mm by default), the CAD convention; Replicator itself is Y-up.
"""
from __future__ import annotations

import datetime as _dt
from pathlib import Path

import numpy as np

from .evaluate import Shape

_UNITS = {"mm": ".MILLI.", "m": None, "cm": ".CENTI."}
_INCH = 25.4


class _Writer:
    def __init__(self):
        self.lines: list[str] = []

    def add(self, entity: str) -> int:
        self.lines.append(entity)
        return len(self.lines)

    def point(self, p) -> int:
        return self.add(f"CARTESIAN_POINT('',({_f(p[0])},{_f(p[1])},{_f(p[2])}))")

    def direction(self, d) -> int:
        return self.add(f"DIRECTION('',({_f(d[0])},{_f(d[1])},{_f(d[2])}))")


def _f(x: float) -> str:
    s = f"{float(x):.10G}"
    if "E" in s:
        m, e = s.split("E")
        return (m if "." in m else m + ".") + "E" + e
    return s if "." in s else s + "."


def _s(text: str) -> str:
    return "'" + text.encode("ascii", "replace").decode().replace("'", "''").replace("\\", "\\\\") + "'"


def _planar_groups(v: np.ndarray, f: np.ndarray, tol: float) -> list[np.ndarray]:
    """Edge-connected triangles that lie in one plane, as lists of triangle indices."""
    n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    ln = np.linalg.norm(n, axis=1)
    ok = ln > 0
    n[ok] /= ln[ok, None]
    d = np.einsum("ij,ij->i", n, v[f[:, 0]])
    # A zero-area sliver (three collinear vertices) cannot be a face of its own, and leaving it out opens the shell.
    # It joins the neighbour across its longest edge; its middle vertex becomes one more point on that face's boundary.
    corner = np.stack([np.linalg.norm(v[f[:, (k + 1) % 3]] - v[f[:, k]], axis=1) for k in range(3)], 1).argmax(1)
    longest = {t: (int(f[t, k]), int(f[t, (k + 1) % 3])) for t, k in enumerate(corner) if not ok[t]}
    parent = np.arange(len(f))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    edges: dict[tuple[int, int], int] = {}
    for t, tri in enumerate(f):
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            o = edges.pop((b, a), None)          # the neighbour across this edge walks it the other way
            if o is None:
                edges[(a, b)] = t
            elif (ok[t] and ok[o] and n[t] @ n[o] > 1 - 1e-9 and abs(d[t] - d[o]) < tol) or \
                    longest.get(t) == (a, b) or longest.get(o) == (b, a):
                ra, rb = find(t), find(o)
                if ra != rb:
                    parent[ra] = rb
    roots = np.array([find(i) for i in range(len(f))])
    order = np.argsort(roots, kind="stable")
    cuts = np.flatnonzero(np.diff(roots[order])) + 1
    return np.split(order, cuts)


def _loops(f: np.ndarray, tris: np.ndarray) -> list[list[int]]:
    """Boundary loops of a planar triangle group, each walked in the triangles' winding (outer CCW, holes CW)."""
    half: dict[tuple[int, int], None] = {}
    for tri in f[tris]:
        for a, b in ((tri[0], tri[1]), (tri[1], tri[2]), (tri[2], tri[0])):
            if (b, a) in half:
                del half[(b, a)]
            else:
                half[(a, b)] = None
    nxt: dict[int, list[int]] = {}
    for a, b in half:
        nxt.setdefault(int(a), []).append(int(b))
    loops = []
    while nxt:
        start = next(iter(nxt))
        loop, cur = [start], start
        while True:
            outs = nxt[cur]
            b = outs.pop()
            if not outs:
                del nxt[cur]
            if b == start:
                break
            loop.append(b)
            cur = b
            if cur not in nxt:          # a broken boundary; never happens on a manifold, guard against a hang
                break
        if len(loop) >= 3:
            loops.append(loop)
    return loops


def _shell(w: _Writer, v: np.ndarray, f: np.ndarray, tol: float) -> int:
    vert_ids: dict[int, int] = {}
    edge_ids: dict[tuple[int, int], int] = {}

    def vertex(i: int) -> int:
        if i not in vert_ids:
            vert_ids[i] = w.add(f"VERTEX_POINT('',#{w.point(v[i])})")
        return vert_ids[i]

    def oriented_edge(a: int, b: int) -> str:
        key = (min(a, b), max(a, b))
        if key not in edge_ids:
            p, q = v[key[0]], v[key[1]]
            d = q - p
            ln = float(np.linalg.norm(d))
            vec = w.add(f"VECTOR('',#{w.direction(d / ln)},{_f(ln)})")
            line = w.add(f"LINE('',#{w.point(p)},#{vec})")
            edge_ids[key] = w.add(f"EDGE_CURVE('',#{vertex(key[0])},#{vertex(key[1])},#{line},.T.)")
        return f"ORIENTED_EDGE('',*,*,#{edge_ids[key]},{'.T.' if a == key[0] else '.F.'})"

    faces = []
    for tris in _planar_groups(v, f, tol):
        loops = _loops(f, tris)
        if not loops:
            continue
        g = f[tris]
        nrm = np.cross(v[g[:, 1]] - v[g[:, 0]], v[g[:, 2]] - v[g[:, 0]]).sum(0)    # area-weighted: sliver-proof
        ln = float(np.linalg.norm(nrm))
        if ln == 0:                      # zero-area group (Manifold drops these; guard anyway)
            continue
        nrm = nrm / ln

        def area(loop):
            p = v[loop]
            return float(np.cross(p, np.roll(p, -1, 0)).sum(0) @ nrm) / 2

        outer = max(range(len(loops)), key=lambda k: area(loops[k]))
        bounds = []
        for k, loop in enumerate(loops):
            es = ",".join(f"#{w.add(oriented_edge(a, b))}" for a, b in zip(loop, loop[1:] + loop[:1]))
            el = w.add(f"EDGE_LOOP('',({es}))")
            bounds.append(w.add(f"{'FACE_OUTER_BOUND' if k == outer else 'FACE_BOUND'}('',#{el},.T.)"))
        p0 = v[loops[outer][0]]
        ref = v[loops[outer][1]] - p0
        ref = ref - (ref @ nrm) * nrm
        if np.linalg.norm(ref) < 1e-12:
            ref = np.cross(nrm, [1.0, 0, 0] if abs(nrm[0]) < 0.9 else [0, 1.0, 0])
        ref = ref / np.linalg.norm(ref)
        ax = w.add(f"AXIS2_PLACEMENT_3D('',#{w.point(p0)},#{w.direction(nrm)},#{w.direction(ref)})")
        plane = w.add(f"PLANE('',#{ax})")
        faces.append(w.add(f"ADVANCED_FACE('',({','.join(f'#{b}' for b in bounds)}),#{plane},.T.)"))
    return w.add(f"CLOSED_SHELL('',({','.join(f'#{x}' for x in faces)}))")


def _arrays(m, scale: float) -> tuple[np.ndarray, np.ndarray]:
    mesh = m.to_mesh()
    v = np.asarray(mesh.vert_properties[:, :3], np.float64) * scale
    return np.column_stack([v[:, 0], -v[:, 2], v[:, 1]]), np.asarray(mesh.tri_verts, np.int64)   # Y-up to Z-up


def _solids(w: _Writer, manifold, name: str, scale: float) -> list[int]:
    """One B-rep solid per connected lump; an internal cavity (a negative lump) becomes a void of the smallest lump
    whose box holds it, so a hollow part keeps its real volume in CAD."""
    lumps = manifold.decompose()
    pos = [m for m in lumps if m.volume() > 0]
    neg = [m for m in lumps if m.volume() < 0]
    box = lambda m: (np.asarray(m.bounding_box()[:3]), np.asarray(m.bounding_box()[3:]))
    voids: dict[int, list] = {i: [] for i in range(len(pos))}
    for c in neg:
        clo, chi = box(c)
        inside = [i for i, m in enumerate(pos) if np.all(box(m)[0] <= clo) and np.all(chi <= box(m)[1])]
        if inside:
            voids[min(inside, key=lambda i: pos[i].volume())].append(c)
    out = []
    for i, m in enumerate(pos):
        v, f = _arrays(m, scale)
        tol = max(float(np.ptp(v, axis=0).max()), 1.0) * 1e-7
        label = name if len(pos) == 1 else f"{name} {i + 1}"
        outer = _shell(w, v, f, tol)
        if not voids[i]:
            out.append(w.add(f"MANIFOLD_SOLID_BREP({_s(label)},#{outer})"))
            continue
        inner = []
        for c in voids[i]:                       # cavity faces point into the hole; STEP wants the shell reversed
            cv, cf = _arrays(c, scale)
            inner.append(w.add(f"ORIENTED_CLOSED_SHELL('',*,#{_shell(w, cv, cf[:, ::-1], tol)},.F.)"))
        out.append(w.add(f"BREP_WITH_VOIDS({_s(label)},#{outer},({','.join(f'#{x}' for x in inner)}))"))
    return out


def write(shapes: list[Shape], path: str | Path, name: str = "Replicator part", units: str = "mm") -> Path:
    """Write the solids to a STEP file. Raises on open surfaces: STEP solids must be closed."""
    path = Path(path)
    bad = [s.id for s in shapes if not hasattr(s.manifold, "status") or s.manifold.status().name != "NoError"
           or s.manifold.is_empty()]
    if bad:
        raise ValueError(f"STEP needs closed solids; these parts are open or broken: {bad}. Export GLB instead")
    scale, unit = (_INCH, ".MILLI.") if units == "in" else (1.0, _UNITS.get(units, ".MILLI."))
    w = _Writer()
    ctx_len = w.add(f"(LENGTH_UNIT() NAMED_UNIT(*) SI_UNIT({unit or '$'},.METRE.))")
    ctx_ang = w.add("(NAMED_UNIT(*) PLANE_ANGLE_UNIT() SI_UNIT($,.RADIAN.))")
    ctx_sol = w.add("(NAMED_UNIT(*) SI_UNIT($,.STERADIAN.) SOLID_ANGLE_UNIT())")
    unc = w.add(f"UNCERTAINTY_MEASURE_WITH_UNIT(LENGTH_MEASURE(1.E-06),#{ctx_len},'distance_accuracy_value','')")
    ctx = w.add(f"(GEOMETRIC_REPRESENTATION_CONTEXT(3) GLOBAL_UNCERTAINTY_ASSIGNED_CONTEXT((#{unc})) "
                f"GLOBAL_UNIT_ASSIGNED_CONTEXT((#{ctx_len},#{ctx_ang},#{ctx_sol})) "
                f"REPRESENTATION_CONTEXT('Context #1','3D Context with UNIT and UNCERTAINTY'))")
    origin = w.add(f"AXIS2_PLACEMENT_3D('',#{w.point((0, 0, 0))},#{w.direction((0, 0, 1))},#{w.direction((1, 0, 0))})")
    solids = []
    for s in shapes:
        solids += _solids(w, s.manifold, s.label or s.id, scale)
    rep = w.add(f"ADVANCED_BREP_SHAPE_REPRESENTATION({_s(name)},(#{origin},{','.join(f'#{x}' for x in solids)}),#{ctx})")
    app = w.add("APPLICATION_CONTEXT('automotive_design')")
    w.add(f"APPLICATION_PROTOCOL_DEFINITION('international standard','automotive_design',2000,#{app})")
    mctx = w.add(f"PRODUCT_CONTEXT('',#{app},'mechanical')")
    prod = w.add(f"PRODUCT({_s(name)},{_s(name)},'',(#{mctx}))")
    w.add(f"PRODUCT_RELATED_PRODUCT_CATEGORY('part',$,(#{prod}))")
    form = w.add(f"PRODUCT_DEFINITION_FORMATION('','',#{prod})")
    dctx = w.add(f"PRODUCT_DEFINITION_CONTEXT('part definition',#{app},'design')")
    pdef = w.add(f"PRODUCT_DEFINITION('design','',#{form},#{dctx})")
    pds = w.add(f"PRODUCT_DEFINITION_SHAPE('','',#{pdef})")
    w.add(f"SHAPE_DEFINITION_REPRESENTATION(#{pds},#{rep})")
    stamp = _dt.datetime.now().replace(microsecond=0).isoformat()
    head = ["ISO-10303-21;", "HEADER;", "FILE_DESCRIPTION(('Replicator faceted B-rep'),'2;1');",
            f"FILE_NAME({_s(path.name)},'{stamp}',(''),(''),'Replicator','Replicator','');",
            "FILE_SCHEMA(('AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }'));", "ENDSEC;", "DATA;"]
    body = [f"#{i}={e};" for i, e in enumerate(w.lines, 1)]
    path.write_text("\n".join(head + body + ["ENDSEC;", "END-ISO-10303-21;", ""]))
    return path
