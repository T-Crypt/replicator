from __future__ import annotations

import math
from typing import Any, Callable

import numpy as np
from manifold3d import Manifold, OpType

Builder = Callable[..., Manifold]


def _eval_error() -> type[ValueError]:
    from .evaluate import EvalError

    return EvalError


def _need_keys(params: dict, required: set[str], name: str) -> None:
    missing = sorted(required - set(params))
    if missing:
        raise _eval_error()(f"{name} needs params {', '.join(missing)}")


def _optional_int(params: dict, key: str, default: int, lo: int, hi: int, name: str) -> int:
    value = int(params.get(key, default))
    if not lo <= value <= hi:
        raise _eval_error()(f"{name} {key} must be {lo}..{hi}")
    return value


def _positive_float(params: dict, key: str, name: str, default: float | None = None) -> float:
    value = float(params[key] if key in params else default)
    if not math.isfinite(value) or value <= 0:
        raise _eval_error()(f"{name} {key} must be a positive finite number")
    return value


def _finite_float(params: dict, key: str, name: str, default: float | None = None) -> float:
    value = float(params[key] if key in params else default)
    if not math.isfinite(value):
        raise _eval_error()(f"{name} {key} must be finite")
    return value


def _mesh_to_manifold(vertices: np.ndarray, triangles: np.ndarray, name: str) -> Manifold:
    V = np.ascontiguousarray(vertices, dtype=np.float32)
    F = np.ascontiguousarray(triangles, dtype=np.uint32)
    if len(F) and len(V):
        area = 0.0
        for tri in F:
            a, b, c = V[tri[0]], V[tri[1]], V[tri[2]]
            area += float(np.dot(a, np.cross(b, c))) / 6.0
        if area < 0:
            F = F[:, ::-1]
    mesh = _make_mesh(V, F)
    m = Manifold(mesh)
    if m.is_empty() or float(m.volume()) <= 0:
        try:
            flipped = Manifold(_make_mesh(V, F[:, ::-1] if len(F) else F))
            if not flipped.is_empty() and float(flipped.volume()) > 0:
                return flipped
        except Exception:
            pass
    raise _eval_error()(f"{name} did not produce a valid non-empty manifold")


def _make_mesh(V: np.ndarray, F: np.ndarray):
    from manifold3d import Mesh

    return Mesh(vert_properties=V, tri_verts=F)


def _resample_polyline(points: np.ndarray, n: int) -> np.ndarray:
    """n points evenly spaced by arc length around a closed ring (a repeated last point is dropped)."""
    if n < 3:
        raise _eval_error_("resample needs at least 3 points")
    ring = np.asarray(points, np.float64).reshape(-1, 3)
    if len(ring) > 1 and np.allclose(ring[0], ring[-1]):
        ring = ring[:-1]
    if len(ring) < 3:
        raise _eval_error_("a section needs at least 3 distinct points")
    closed = np.vstack([ring, ring[:1]])
    seg = np.linalg.norm(np.diff(closed, axis=0), axis=1)
    cum = np.r_[0.0, np.cumsum(seg)]
    if cum[-1] <= 0:
        raise _eval_error_("a section has zero length")
    t = np.linspace(0.0, cum[-1], n, endpoint=False)
    return np.column_stack([np.interp(t, cum, closed[:, k]) for k in range(3)])


def _eval_error_(msg: str):
    raise _eval_error()(msg)


def _section_points(sec: dict, name: str) -> np.ndarray:
    if not isinstance(sec, dict):
        raise _eval_error_(f"{name} sections must be dicts")
    if "y" not in sec:
        raise _eval_error_(f"{name} sections need y")
    if "radius" in sec:
        r = float(sec["radius"])
        if r <= 0:
            raise _eval_error_(f"{name} radius must be > 0")
        theta = np.linspace(0.0, 2.0 * math.pi, 256, endpoint=False)
        return np.column_stack([r * np.cos(theta), np.zeros_like(theta), r * np.sin(theta)])
    if "rx" in sec or "rz" in sec:
        rx = float(sec.get("rx", sec.get("rz", 1.0)))
        rz = float(sec.get("rz", sec.get("rx", 1.0)))
        if rx <= 0 or rz <= 0:
            raise _eval_error_(f"{name} rx and rz must be > 0")
        theta = np.linspace(0.0, 2.0 * math.pi, 256, endpoint=False)
        return np.column_stack([rx * np.cos(theta), np.zeros_like(theta), rz * np.sin(theta)])
    pts = sec.get("points")
    if not isinstance(pts, (list, tuple)) or len(pts) < 3:
        raise _eval_error_(f"{name} polygon sections need at least 3 points")
    arr = []
    for p in pts:
        if not (isinstance(p, (list, tuple)) and len(p) == 2):
            raise _eval_error_(f"{name} polygon points must be [x, z]")
        arr.append([float(p[0]), float(p[1])])
    arr = np.asarray(arr, dtype=np.float64)
    if np.allclose(arr[0], arr[-1], rtol=1e-8, atol=1e-9):
        arr = arr[:-1]
    if len(arr) < 3:
        raise _eval_error_(f"{name} polygon sections need at least 3 distinct points")
    return np.column_stack([arr[:, 0], np.zeros_like(arr[:, 0]), arr[:, 1]])


def _section_signed_area_z(pts3: np.ndarray) -> float:
    x = pts3[:, 0]
    z = pts3[:, 2]
    xn = np.roll(x, -1)
    zn = np.roll(z, -1)
    return float(np.sum(x * zn - xn * z))


def _rotate_section_to_start_max_x(pts3: np.ndarray) -> np.ndarray:
    if len(pts3) == 0:
        return pts3
    idx = int(np.argmax(pts3[:, 0]))
    return np.roll(pts3, -idx, axis=0)


def _orient_for_loft(pts3: np.ndarray, want_positive_z: bool) -> np.ndarray:
    # A polygon ordered as angle increasing in (x,z) gives -Y planar normal.
    # For +Y caps we need the reverse order; for -Y caps we keep it.
    area = _section_signed_area_z(pts3)
    if area == 0:
        return pts3
    positive_standard = area > 0
    if want_positive_z and positive_standard:
        return pts3[::-1]
    if not want_positive_z and not positive_standard:
        return pts3[::-1]
    return pts3


def _build_loft(params: dict) -> Manifold:
    """Skin closed sections stacked along +Y into a solid. Every section is resampled to the same point count,
    starting at its max-x point, so the rings line up; caps are triangulated."""
    _need_keys(params, {"sections"}, "loft")
    sections = params["sections"]
    if not isinstance(sections, (list, tuple)) or len(sections) < 2:
        raise _eval_error_("loft sections must be a list with at least 2 entries")
    n = _optional_int(params, "segments", 48, 3, 512, "loft")
    rings, ys = [], []
    for i, sec in enumerate(sections):
        if not isinstance(sec, dict) or "y" not in sec:
            raise _eval_error_(f"loft sections[{i}] needs a y")
        p = _rotate_section_to_start_max_x(_resample_polyline(_section_points(sec, f"loft sections[{i}]"), n))
        xz = np.column_stack([p[:, 0], p[:, 2]])
        area = 0.5 * np.sum(xz[:, 0] * np.roll(xz[:, 1], -1) - np.roll(xz[:, 0], -1) * xz[:, 1])
        if area < 0:                                   # one winding for every ring, keeping the max-x start
            xz = np.vstack([xz[:1], xz[1:][::-1]])
        y = float(sec["y"])
        if not math.isfinite(y):
            raise _eval_error_("loft section y must be finite")
        ys.append(y)
        rings.append(np.column_stack([xz[:, 0], np.full(n, y), xz[:, 1]]))
    if np.any(np.diff(ys) <= 0):
        raise _eval_error_("loft section y values must be strictly increasing")
    from manifold3d import triangulate
    V = np.vstack(rings)
    side = []
    for r in range(len(rings) - 1):
        for i in range(n):
            j = (i + 1) % n
            b0, b1, t0, t1 = r * n + i, r * n + j, (r + 1) * n + i, (r + 1) * n + j
            side += [[b0, t0, b1], [t0, t1, b1]]
    cap = np.asarray(triangulate([rings[0][:, [0, 2]].tolist()]), np.int64)
    bottom = cap.tolist()
    top = (cap[:, ::-1] + (len(rings) - 1) * n).tolist()
    side = np.asarray(side, np.int64)
    for flip_side in (False, True):                    # pick the consistent orientation with positive volume
        for flip_caps in (False, True):
            S = side[:, ::-1] if flip_side else side
            B = np.asarray(bottom)[:, ::-1] if flip_caps else np.asarray(bottom)
            T = np.asarray(top)[:, ::-1] if flip_caps else np.asarray(top)
            try:
                m = Manifold(_make_mesh(V, np.vstack([S, B, T])))
            except Exception:  # noqa: BLE001
                continue
            if not m.is_empty() and m.status().name == "NoError" and float(m.volume()) > 0:
                return m
    raise _eval_error_("loft sections do not form a closed solid (self-crossing or degenerate sections?)")


def _catmull_rom(points: np.ndarray, points_per_span: int) -> np.ndarray:
    pts = points.reshape(-1, 3)
    if len(pts) < 2:
        raise _eval_error_("pipe path must have at least 2 points")
    if points_per_span < 1:
        raise _eval_error_("pipe smooth must be positive")
    if len(pts) == 2:
        t = np.linspace(0.0, 1.0, points_per_span)
        return pts[0] + t[:, None] * (pts[1] - pts[0])
    padded = np.vstack([pts[0:1], pts, pts[-1:]])
    out = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for j in range(points_per_span):
            t = j / points_per_span
            t2 = t * t
            t3 = t2 * t
            out.append(
                0.5
                * (
                    2.0 * p1
                    + (p2 - p0) * t
                    + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                    + (3.0 * (p1 - p2) + p3 - p0) * t3
                )
            )
    out.append(pts[-1].copy())
    return np.asarray(out, dtype=np.float64)


def _build_pipe(params: dict) -> Manifold:
    _need_keys(params, {"path", "radius"}, "pipe")
    path = params["path"]
    if not isinstance(path, (list, tuple)) or len(path) < 2:
        raise _eval_error_("pipe path must be a list of at least 2 [x, y, z] points")
    arr = []
    for p in path:
        if not (isinstance(p, (list, tuple)) and len(p) == 3):
            raise _eval_error_("pipe path points must be [x, y, z]")
        arr.append([float(p[0]), float(p[1]), float(p[2])])
    arr = np.asarray(arr, dtype=np.float64)
    if np.any(~np.isfinite(arr)):
        raise _eval_error_("pipe path points must be finite")

    r = _positive_float(params, "radius", "pipe")
    smooth = _optional_int(params, "smooth", 0, 0, 64, "pipe")
    segs = _optional_int(params, "segments", 16, 3, 256, "pipe")

    if smooth > 0:
        path_pts = _catmull_rom(arr, smooth)
    else:
        path_pts = arr
    if len(path_pts) > 6000:
        raise _eval_error_("pipe path is too long (over 6000 segments): fewer points or less smooth")

    parts = []
    for i in range(len(path_pts) - 1):
        s0 = Manifold.sphere(r, segs).translate(path_pts[i].tolist())
        s1 = Manifold.sphere(r, segs).translate(path_pts[i + 1].tolist())
        parts.append(Manifold.batch_hull([s0, s1]))
    if len(parts) == 1:
        m = parts[0]
    else:
        m = Manifold.batch_boolean(parts, OpType.Add)
    if m.is_empty() or float(m.volume()) <= 0:
        raise _eval_error_("pipe did not produce a valid non-empty manifold")
    return m


def _build_helix(params: dict) -> Manifold:
    _need_keys(params, {"radius", "pitch", "turns", "wire_radius"}, "helix")
    radius = _positive_float(params, "radius", "helix")
    pitch = _finite_float(params, "pitch", "helix")
    if pitch == 0:
        raise _eval_error_("helix pitch must be non-zero")
    turns = _finite_float(params, "turns", "helix")
    if not 1e-9 < abs(turns) <= 200:
        raise _eval_error_("helix turns must be non-zero and at most 200")
    wire = _positive_float(params, "wire_radius", "helix")
    segs = _optional_int(params, "segments", 16, 3, 256, "helix")
    pts_per_turn = max(24, segs)
    total_pts = max(48, int(math.ceil(abs(turns) * pts_per_turn)) + 1)
    t = np.linspace(0.0, turns * 2.0 * math.pi, total_pts)
    path = np.column_stack([radius * np.cos(t), pitch * t / (2.0 * math.pi), radius * np.sin(t)])
    return _build_pipe({"path": path.tolist(), "radius": wire, "segments": segs})


def _involute_gear_profile(params: dict) -> np.ndarray:
    """Closed CCW polygon [(x, z)] of a standard spur gear: involute flanks from the base (or root) circle to the
    tip circle, tip arcs and root arcs. Pitch r = m*z/2, addendum m, dedendum 1.25 m."""
    teeth = int(params["teeth"])
    if teeth < 6 or teeth > 200:
        raise _eval_error_("gear teeth must be 6..200")
    m = _positive_float(params, "module", "gear")
    pa = float(params.get("pressure_angle", 20.0))
    if not math.isfinite(pa) or not (5.0 <= pa <= 35.0):
        raise _eval_error_("gear pressure_angle must be 5..35 degrees")
    n = 8                                     # points per flank (segments is the bore circle's resolution)
    alpha = math.radians(pa)
    rp = m * teeth / 2.0
    rb = rp * math.cos(alpha)
    ra = rp + m
    rf = max(rp - 1.25 * m, 0.3 * rp)
    inv = lambda a: math.tan(a) - a  # noqa: E731
    # half the tooth's angular thickness at the pitch circle is pi/(2z); shift to the base-circle involute origin
    half_pitch = math.pi / (2 * teeth)
    origin = half_pitch + inv(alpha)          # angle of the involute start (on the base circle) from tooth centre
    r_start = max(rb, rf)

    def flank(sign: int) -> list[tuple[float, float]]:
        pts = []
        for k in range(n + 1):
            r = r_start + (ra - r_start) * k / n
            a_r = math.acos(min(1.0, rb / r))
            theta = origin - inv(a_r)          # half-angle of the tooth at radius r
            pts.append((r, sign * theta))
        return pts

    poly: list[tuple[float, float]] = []
    step = 2 * math.pi / teeth
    for t in range(teeth):
        c = t * step
        right = flank(-1)                      # from root up the trailing side
        left = flank(+1)[::-1]                 # down the leading side
        tooth = [(r, c + a) for r, a in right] + [(r, c + a) for r, a in left]
        if rf < rb:                            # radial line from the root circle to the base circle
            tooth = [(rf, tooth[0][1])] + tooth + [(rf, tooth[-1][1])]
        poly.extend(tooth)
        # root arc to the next tooth
        a0, a1 = tooth[-1][1], c + step + (tooth[0][1] - c)
        for k in range(1, 4):
            poly.append((rf, a0 + (a1 - a0) * k / 4))
    pts = np.array([[r * math.cos(a), r * math.sin(a)] for r, a in poly])
    area = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    return pts if area > 0 else pts[::-1]


def _build_gear(params: dict) -> Manifold:
    _need_keys(params, {"teeth", "module", "thickness"}, "gear")
    teeth = int(params["teeth"])
    if teeth < 6 or teeth > 200:
        raise _eval_error_("gear teeth must be 6..200")
    module = _positive_float(params, "module", "gear")
    thickness = _positive_float(params, "thickness", "gear")
    bore = params.get("bore", 0.0)
    bore = float(bore)
    if bore < 0:
        raise _eval_error_("gear bore must be >= 0")

    prof = _involute_gear_profile(params)
    xs, zs = prof[:, 0], prof[:, 1]
    max_r = float(np.hypot(xs, zs).max())
    if bore >= max_r:
        raise _eval_error_("gear bore must be smaller than the gear root radius")

    # Extrude in Z then rotate to Y. CrossSection expects XY; our profile is XZ, so map x->x, z->y.
    from manifold3d import CrossSection

    poly = [[float(x), float(z)] for x, z in prof]
    holes = []
    if bore > 0:
        m = _optional_int(params, "segments", 64, 12, 512, "gear")
        theta = np.linspace(0.0, 2.0 * math.pi, m, endpoint=False)
        holes.append([[bore * math.cos(t), bore * math.sin(t)] for t in theta])

    m = Manifold.extrude(CrossSection([poly] + holes), thickness, n_divisions=0, twist_degrees=0.0, scale_top=[1.0, 1.0])
    m = m.translate((0.0, 0.0, -thickness / 2.0))
    m = m.rotate((-90.0, 0.0, 0.0))
    if m.is_empty() or float(m.volume()) <= 0:
        raise _eval_error_("gear did not produce a valid non-empty manifold")
    return m


def _axis_index(axis, name: str) -> int:
    if isinstance(axis, str):
        a = axis.strip().lower().lstrip("+-")
        if a in ("x", "y", "z"):
            return "xyz".index(a)
        raise _eval_error_("deform axis must be x, y or z")
    if isinstance(axis, (list, tuple)) and len(axis) == 3:
        vals = [abs(float(v)) for v in axis]
        if sorted(vals)[:2] == [0.0, 0.0] and max(vals) > 0:
            return vals.index(max(vals))
        raise _eval_error_("deform axis must be axis-aligned")
    raise _eval_error_("deform axis must be x, y or z")


def _build_deform(params: dict, m: Manifold) -> Manifold:
    _need_keys(params, {"mode", "amount"}, "deform")
    mode = str(params["mode"]).lower()
    if mode not in ("taper", "twist", "bend"):
        raise _eval_error_("deform mode must be taper, twist or bend")
    amount = float(params["amount"])
    if not math.isfinite(amount):
        raise _eval_error_("deform amount must be finite")
    if mode == "taper" and (amount <= 0):
        raise _eval_error_("deform taper amount must be > 0")
    idx = _axis_index(params.get("axis", "y"), "deform")

    bb = np.asarray(m.bounding_box(), dtype=np.float64)
    lo, hi = bb[:3], bb[3:]
    size = hi - lo
    extent = float(size[idx])
    if extent <= 0:
        raise _eval_error_("deform input has zero extent along the deformation axis")
    res = params.get("resolution")
    if res is None:
        res = extent / 48.0
    else:
        res = float(res)
        if not res >= extent / 400.0:
            raise _eval_error_(f"deform resolution must be at least {extent / 400.0:.3g} (1/400 of the part)")
    refined = m.refine_to_length(res)

    center = (lo + hi) / 2.0
    min_end = lo[idx]
    max_end = hi[idx]

    others = [j for j in range(3) if j != idx]
    if mode == "taper":
        def warp(P: np.ndarray) -> np.ndarray:
            P = P.copy()
            t = np.clip((P[:, idx] - min_end) / extent, 0.0, 1.0)
            scale = 1.0 + (amount - 1.0) * t
            for j in others:
                P[:, j] = center[j] + scale * (P[:, j] - center[j])
            return P
    elif mode == "twist":
        def warp(P: np.ndarray) -> np.ndarray:
            P = P.copy()
            t = np.clip((P[:, idx] - min_end) / extent, 0.0, 1.0)
            th = np.radians(amount * t)
            a, b = others
            x, z = P[:, a] - center[a], P[:, b] - center[b]
            P[:, a] = center[a] + np.cos(th) * x - np.sin(th) * z
            P[:, b] = center[b] + np.sin(th) * x + np.cos(th) * z
            return P
    else:
        # Bend the axis into an arc of `amount` degrees. The neutral axis passes through the centre; a point at
        # offset d from it (along the bend direction) lands on radius R - d, so volume is kept to first order.
        if abs(amount) < 1e-6:
            return m
        theta_total = math.radians(amount)
        R = extent / theta_total
        bend_dir = max(others, key=lambda j: float(size[j]))   # bend in the plane of the wider cross-section side
        def warp(P: np.ndarray) -> np.ndarray:
            P = P.copy()
            th = (P[:, idx] - min_end) / R
            d = P[:, bend_dir] - center[bend_dir]
            P[:, idx] = min_end + (R - d) * np.sin(th)
            P[:, bend_dir] = center[bend_dir] + R - (R - d) * np.cos(th)
            return P
    warped = refined.warp_batch(warp)
    if warped.is_empty() or float(warped.volume()) <= 0:
        raise _eval_error_("deform did not produce a valid non-empty manifold")
    return warped


def _wrap_builder(builder: Builder) -> Builder:
    def wrapped(*args, **kwargs):
        try:
            return builder(*args, **kwargs)
        except Exception as e:
            if isinstance(e, _eval_error()):
                raise
            raise _eval_error_(str(e))
    return wrapped


PRIMITIVES: dict[str, tuple[set[str], set[str], Builder]] = {
    "loft": ({"sections"}, {"segments", "closed_caps"}, _wrap_builder(_build_loft)),
    "pipe": ({"path", "radius"}, {"segments", "smooth"}, _wrap_builder(_build_pipe)),
    "helix": ({"radius", "pitch", "turns", "wire_radius"}, {"segments"}, _wrap_builder(_build_helix)),
    "gear": ({"teeth", "module", "thickness"}, {"bore", "pressure_angle", "segments"}, _wrap_builder(_build_gear)),
}

MODIFIERS: dict[str, tuple[set[str], set[str], Builder]] = {
    "deform": ({"mode", "amount"}, {"axis", "resolution"}, _wrap_builder(_build_deform)),
}
