"""Engineering ops: shapes a local model gets wrong when it builds them from boxes and cylinders.

Each op takes the numbers an engineer would quote (a throat radius and an expansion ratio, a hub and tip radius) and
the code draws the contour, so the proportions come from the formula and not from the model's memory.
All four are centred on the origin with their axis along Y, like `cylinder`.
"""
from __future__ import annotations

import math

import numpy as np
from manifold3d import CrossSection, Manifold, OpType

from .ops_advanced import _optional_int, _positive_float, _wrap_builder

Z_TO_Y = (-90.0, 0.0, 0.0)


def _err(msg: str):
    from .evaluate import EvalError
    return EvalError(msg)


def _lathe(points: list[tuple[float, float]], segments: int) -> Manifold:
    """[radius, y] profile spun around Y, whichever way it winds."""
    pts = np.asarray(points, float)
    area = 0.5 * np.sum(pts[:, 0] * np.roll(pts[:, 1], -1) - np.roll(pts[:, 0], -1) * pts[:, 1])
    if area < 0:
        pts = pts[::-1]
    return Manifold.revolve(CrossSection([pts.tolist()]), segments).rotate(Z_TO_Y)


def _build_tube(p: dict) -> Manifold:
    """A hollow cylinder or cone frustum: casings, nacelles, liners, pipes, sleeves."""
    h = _positive_float(p, "height", "tube")
    ro = _positive_float(p, "radius", "tube")
    rt = _positive_float(p, "radius_top", "tube", ro)
    w = _positive_float(p, "wall", "tube")
    if w >= min(ro, rt):
        raise _err("tube wall must be thinner than the radius (use cylinder for a solid)")
    n = _optional_int(p, "segments", 96, 8, 512, "tube")
    return _lathe([(ro - w, -h / 2), (ro, -h / 2), (rt, h / 2), (rt - w, h / 2)], n)


# Rao's thrust-optimised parabola, 80 % bell: start and exit wall angles (degrees) against expansion ratio.
# Read off the usual design chart (Huzel and Huang); good to a degree or two, which is plenty for a model.
_RAO_EPS = [4, 5, 10, 20, 40, 60, 100]
_RAO_THETA_N = [24.0, 26.0, 30.0, 32.5, 34.5, 35.5, 36.5]
_RAO_THETA_E = [11.0, 10.0, 8.5, 7.5, 6.5, 6.0, 5.5]


def nozzle_contour(rt: float, eps: float, cr: float, lc: float | None, frac: float, n: int = 40) -> np.ndarray:
    """Inner wall [(x, r)] of a rocket thrust chamber, x along the flow, throat at x = 0. Chamber cylinder, a 30 degree
    converging cone with a 1.5 Rt throat arc, a 0.382 Rt arc after the throat, then a quadratic Bezier bell."""
    re, rc = rt * math.sqrt(eps), rt * math.sqrt(cr)
    theta_c = math.radians(30.0)
    le = math.log(min(max(eps, _RAO_EPS[0]), _RAO_EPS[-1]))
    tn = math.radians(np.interp(le, np.log(_RAO_EPS), _RAO_THETA_N))
    te = math.radians(np.interp(le, np.log(_RAO_EPS), _RAO_THETA_E))
    ln = frac * (math.sqrt(eps) - 1) * rt / math.tan(math.radians(15.0))

    a = np.linspace(theta_c, 0, n // 2)                       # converging throat arc, upstream side
    conv_arc = np.column_stack([-1.5 * rt * np.sin(a), rt + 1.5 * rt * (1 - np.cos(a))])
    x0, r0 = conv_arc[0]
    cone_len = (rc - r0) / math.tan(theta_c)
    lc = 2.0 * rc if lc is None else lc
    x_cone = x0 - cone_len
    chamber = np.array([[x_cone - lc, rc], [x_cone, rc]])

    b = np.linspace(0, tn, n // 3)[1:]                         # diverging throat arc
    div_arc = np.column_stack([0.382 * rt * np.sin(b), rt + 0.382 * rt * (1 - np.cos(b))])
    nx, nr = div_arc[-1]
    ex, er = ln, re
    qx = (er - nr + nx * math.tan(tn) - ex * math.tan(te)) / (math.tan(tn) - math.tan(te))
    qr = nr + (qx - nx) * math.tan(tn)
    t = np.linspace(0, 1, n)[1:, None]
    bell = (1 - t) ** 2 * [nx, nr] + 2 * (1 - t) * t * [qx, qr] + t ** 2 * [ex, er]
    return np.vstack([chamber, conv_arc, div_arc, bell])


def _build_nozzle(p: dict) -> Manifold:
    """A rocket thrust chamber and bell nozzle: injector face at +Y (closed), exit at -Y (open)."""
    rt = _positive_float(p, "throat_radius", "nozzle")
    eps = _positive_float(p, "expansion_ratio", "nozzle")
    cr = _positive_float(p, "contraction_ratio", "nozzle", 4.0)
    if eps <= 1.5 or cr <= 1.2:
        raise _err("nozzle expansion_ratio must be > 1.5 and contraction_ratio > 1.2")
    lc = _positive_float(p, "chamber_length", "nozzle") if "chamber_length" in p else None
    frac = _positive_float(p, "bell_fraction", "nozzle", 0.8)
    w = _positive_float(p, "wall", "nozzle", max(rt * 0.08, 0.5))
    n = _optional_int(p, "segments", 96, 16, 512, "nozzle")
    inner = nozzle_contour(rt, eps, cr, lc, frac)
    x_top, x_exit = inner[0, 0] - w, inner[-1, 0]
    outer = inner[::-1].copy()
    outer[:, 1] += w
    prof = [(0.0, x_top), (inner[0, 1] + w, x_top)] + [(r, x) for x, r in outer[::-1]]
    prof += [(r, x) for x, r in inner[::-1]] + [(0.0, inner[0, 0])]
    mid = (x_top + x_exit) / 2
    return _lathe([(r, -(x - mid)) for r, x in prof], n)


def _naca(t: float, n: int = 24) -> list[list[float]]:
    """Symmetric NACA 00xx section, unit chord centred on its quarter chord; x along the chord, y thickness."""
    x = (1 - np.cos(np.linspace(0, math.pi, n))) / 2
    yt = 5 * t * (0.2969 * np.sqrt(x) - 0.126 * x - 0.3516 * x ** 2 + 0.2843 * x ** 3 - 0.1036 * x ** 4)
    upper = np.column_stack([x, yt])[::-1]
    lower = np.column_stack([x, -yt])[1:-1]
    pts = np.vstack([upper, lower])
    pts[:, 0] -= 0.25
    return pts.tolist()


def _build_rotor(p: dict) -> Manifold:
    """Hub plus twisted, tapered airfoil blades in the XZ plane, spinning about Y: fans, compressors, turbines,
    propellers. `pitch` is the blade angle at the root, `twist` how much it flattens out by the tip."""
    rh = _positive_float(p, "hub_radius", "rotor")
    rtip = _positive_float(p, "tip_radius", "rotor")
    if rtip <= rh:
        raise _err("rotor tip_radius must be larger than hub_radius")
    count = _optional_int(p, "blades", 12, 2, 128, "rotor")
    chord = _positive_float(p, "chord", "rotor")
    tip_chord = _positive_float(p, "tip_chord", "rotor", chord * 0.7)
    pitch = float(p.get("pitch", 40.0))
    twist = float(p.get("twist", 25.0))
    t = _positive_float(p, "thickness", "rotor", 0.10)
    hub_len = _positive_float(p, "hub_length", "rotor", chord * 1.3)
    root = rh * 0.92
    span = rtip - root
    sec = CrossSection([_naca(min(t, 0.3))]).scale((chord, chord)).rotate(pitch)
    blade = Manifold.extrude(sec, span, n_divisions=max(4, int(abs(twist) // 4)), twist_degrees=-twist,
                             scale_top=(tip_chord / chord, tip_chord / chord))
    blade = blade.rotate((0.0, 90.0, 0.0)).translate((root, 0.0, 0.0))
    blades = [blade.rotate((0.0, 360.0 * i / count, 0.0)) for i in range(count)]
    hub = Manifold.cylinder(hub_len, rh, rh, 64, center=True).rotate(Z_TO_Y)
    return Manifold.batch_boolean([hub, *blades], OpType.Add)


HOLES = ("round", "hex", "slot")


def _build_grille(p: dict) -> Manifold:
    """A perforated plate in the XZ plane, thickness along Y: case vents, speaker and fan grilles, heat-sink covers."""
    size = p.get("size")
    if not (isinstance(size, list) and len(size) == 3):
        raise _err("grille size is [width, thickness, depth]")
    sx, sy, sz = (float(v) for v in size)
    d = _positive_float(p, "hole_size", "grille")
    pitch = _positive_float(p, "pitch", "grille", d * 1.5)
    if pitch <= d:
        raise _err("grille pitch must be larger than hole_size")
    shape = p.get("hole", "hex")
    if shape not in HOLES:
        raise _err(f"grille hole must be one of {HOLES}")
    margin = float(p.get("margin", pitch))
    plate = Manifold.cube((sx, sy, sz), center=True)
    if shape == "slot":
        cutter = Manifold.cube((d, sy * 3, sz - 2 * margin), center=True)
        xs = np.arange(-sx / 2 + margin + d / 2, sx / 2 - margin - d / 2 + 1e-9, pitch)
        holes = [cutter.translate((float(x), 0.0, 0.0)) for x in xs]
    else:
        seg = 6 if shape == "hex" else 32
        cutter = Manifold.cylinder(sy * 3, d / 2, d / 2, seg, center=True).rotate(Z_TO_Y)
        row = pitch * (math.sqrt(3) / 2 if shape == "hex" else 1.0)
        holes = []
        for j, z in enumerate(np.arange(-sz / 2 + margin, sz / 2 - margin + 1e-9, row)):
            shift = pitch / 2 if shape == "hex" and j % 2 else 0.0
            for x in np.arange(-sx / 2 + margin + shift, sx / 2 - margin + 1e-9, pitch):
                holes.append(cutter.translate((float(x), 0.0, float(z))))
    if not holes:
        raise _err("grille has no room for holes: lower margin or hole_size")
    if len(holes) > 4000:
        raise _err("grille would cut over 4000 holes; raise pitch")
    return plate - Manifold.batch_boolean(holes, OpType.Add)


PRIMITIVES = {
    "tube": ({"height", "radius", "wall"}, {"radius_top", "segments"}, _wrap_builder(_build_tube)),
    "nozzle": ({"throat_radius", "expansion_ratio"},
               {"contraction_ratio", "chamber_length", "bell_fraction", "wall", "segments"},
               _wrap_builder(_build_nozzle)),
    "rotor": ({"hub_radius", "tip_radius", "chord"},
              {"blades", "tip_chord", "pitch", "twist", "thickness", "hub_length"}, _wrap_builder(_build_rotor)),
    "grille": ({"size", "hole_size"}, {"pitch", "hole", "margin"}, _wrap_builder(_build_grille)),
}
