#!/usr/bin/env python3
"""Draw the README artwork: assets/banner.svg and assets/how-it-works.svg.

Hand-tuned SVG, generated so the engine geometry stays consistent between the wireframe and solid passes.
Run: python3 tools/readme_art.py   (no dependencies)
"""
from __future__ import annotations

from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

CY = "#7ad4f2"     # holo cyan
AM = "#e8b56f"     # amber
BL = "#3a8ee6"     # app accent blue
INK = "#f0f5fa"
DIM = "#8ba0b8"
LINE = "#243549"
MONO = "ui-monospace,'JetBrains Mono','SF Mono',Menlo,Consolas,'DejaVu Sans Mono',monospace"
SANS = "system-ui,-apple-system,'Segoe UI',Inter,'Helvetica Neue',Arial,'DejaVu Sans',sans-serif"

STYLE = f"""
  .m{{font-family:{MONO}}} .s{{font-family:{SANS}}}
  .flow{{stroke-dasharray:6 8;animation:flow 1.6s linear infinite}}
  @keyframes flow{{to{{stroke-dashoffset:-28}}}}
  .pulse{{animation:pulse 2.4s ease-in-out infinite}}
  @keyframes pulse{{0%,100%{{opacity:.45}}50%{{opacity:1}}}}
  .blink{{animation:blink 1.1s steps(1) infinite}}
  @keyframes blink{{50%{{opacity:0}}}}
  .float{{animation:float 6s ease-in-out infinite}}
  @keyframes float{{0%,100%{{transform:translateY(0)}}50%{{transform:translateY(-5px)}}}}
  @media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
"""


# --------------------------------------------------------------------------- engine geometry (side view, axis along x)

def cyl(x0: float, r0: float, x1: float, r1: float, c: float, k: float = .3) -> tuple[str, str, str]:
    """Body outline, front face ellipse and back rim of a (tapered) cylinder seen from the front-left."""
    body = (f"M{x0:.1f},{c - r0:.1f} L{x1:.1f},{c - r1:.1f} A{k * r1:.1f},{r1:.1f} 0 0 1 {x1:.1f},{c + r1:.1f} "
            f"L{x0:.1f},{c + r0:.1f} A{k * r0:.1f},{r0:.1f} 0 0 1 {x0:.1f},{c - r0:.1f}Z")
    face = f'cx="{x0:.1f}" cy="{c:.1f}" rx="{k * r0:.1f}" ry="{r0:.1f}"'
    rim = f"M{x1:.1f},{c - r1:.1f} A{k * r1:.1f},{r1:.1f} 0 0 1 {x1:.1f},{c + r1:.1f}"
    return body, face, rim


# (label, x0, r0, x1, r1, colour, extra) - exploded along the axis
PARTS = [
    ("Intake cowl", 0, 96, 92, 92, "#a7c97a", "ring"),
    ("Fan blade set", 122, 80, 134, 80, "#e06b7b", "blades"),
    ("Core compressor", 162, 62, 246, 50, "#b98be0", "ribs"),
    ("Combustor annulus", 272, 56, 300, 56, "#7ee8ac", ""),
    ("Turbine stage", 326, 47, 366, 44, "#e88b4f", "ribs"),
    ("Exhaust nozzle", 392, 42, 458, 27, "#e8c46f", ""),
]


def engine(ox: float, c: float, wire: bool, scale: float = 1.0) -> str:
    out = []
    for name, x0, r0, x1, r1, col, extra in PARTS:
        x0, x1 = ox + x0 * scale, ox + x1 * scale
        r0, r1 = r0 * scale, r1 * scale
        body, face, rim = cyl(x0, r0, x1, r1, c)
        if wire:
            out.append(f'<path d="{body}" fill="{CY}" fill-opacity=".05" stroke="{CY}" stroke-width="1.2" stroke-opacity=".85"/>')
            # hidden-line hatching: rings along the body
            n = max(2, int((x1 - x0) / 9))
            for i in range(1, n):
                t = i / n
                x, r = x0 + (x1 - x0) * t, r0 + (r1 - r0) * t
                out.append(f'<path d="M{x:.1f},{c - r:.1f} A{.3 * r:.1f},{r:.1f} 0 0 1 {x:.1f},{c + r:.1f}" '
                           f'fill="none" stroke="{CY}" stroke-width=".6" stroke-opacity=".35"/>')
            out.append(f'<ellipse {face} fill="#071725" stroke="{CY}" stroke-width="1.3"/>')
        else:
            out.append(f'<path d="{body}" fill="url(#sh-{col[1:]})" stroke="#0b1420" stroke-width="1"/>')
            out.append(f'<path d="{rim}" fill="none" stroke="#000" stroke-opacity=".25" stroke-width="2"/>')
            out.append(f'<ellipse {face} fill="{col}" stroke="#0b1420" stroke-width="1"/>')
            out.append(f'<ellipse {face} fill="url(#spec)" />')
        stroke = CY if wire else "#0b1420"
        fx, fr = x0, r0
        if extra == "ring":   # the intake mouth and the fan hub inside it
            out.append(f'<ellipse cx="{fx + 2:.1f}" cy="{c}" rx="{.3 * fr * .72:.1f}" ry="{fr * .72:.1f}" '
                       f'fill="{"#071725" if wire else "#16202c"}" stroke="{stroke}" stroke-width="1.2"/>')
            out.append(f'<ellipse cx="{fx + 6:.1f}" cy="{c}" rx="{.3 * fr * .22:.1f}" ry="{fr * .22:.1f}" '
                       f'fill="{"none" if wire else "#7ad4f2"}" stroke="{stroke}" stroke-width="1"/>')
            # status glow arc
            out.append(f'<path d="M{fx - 12:.1f},{c + fr * .45:.1f} A{.3 * fr * .6:.1f},{fr * .6:.1f} 0 0 0 {fx + 14:.1f},{c + fr * .5:.1f}" '
                       f'fill="none" stroke="{CY}" stroke-width="{2 if wire else 4}" stroke-linecap="round" class="pulse"/>')
        if extra == "blades":
            for i in range(12):
                import math
                a = math.pi * 2 * i / 12
                y = c + math.sin(a) * fr * .92
                dx = math.cos(a) * .3 * fr * .92
                out.append(f'<line x1="{fx:.1f}" y1="{c}" x2="{fx + dx:.1f}" y2="{y:.1f}" stroke="{CY if wire else "#5a1f2a"}" '
                           f'stroke-width="{1 if wire else 2.2}" stroke-opacity=".8"/>')
        if extra == "ribs" and not wire:
            n = int((x1 - x0) / 10)
            for i in range(1, n):
                t = i / n
                x, r = x0 + (x1 - x0) * t, r0 + (r1 - r0) * t
                out.append(f'<path d="M{x:.1f},{c - r:.1f} A{.3 * r:.1f},{r:.1f} 0 0 1 {x:.1f},{c + r:.1f}" '
                           f'fill="none" stroke="#000" stroke-opacity=".18" stroke-width="1"/>')
    return "\n".join(out)


def shade_defs() -> str:
    out = []
    for *_, col, _ in PARTS:
        out.append(f'<linearGradient id="sh-{col[1:]}" x1="0" y1="0" x2="0" y2="1">'
                   f'<stop offset="0" stop-color="{col}" stop-opacity=".55"/><stop offset=".28" stop-color="{col}"/>'
                   f'<stop offset=".62" stop-color="{col}" stop-opacity=".78"/><stop offset="1" stop-color="#0b1420" stop-opacity=".9"/>'
                   f'</linearGradient>')
    out.append('<radialGradient id="spec" cx=".35" cy=".3" r=".7"><stop offset="0" stop-color="#fff" stop-opacity=".35"/>'
               '<stop offset="1" stop-color="#fff" stop-opacity="0"/></radialGradient>')
    return "\n".join(out)


def floor(x0: float, x1: float, y0: float, y1: float, vx: float, vy: float, n: int = 22, rows: int = 9) -> str:
    """Perspective workshop floor: rays to a vanishing point plus receding rows."""
    out = []
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / n
        # ray from the bottom edge toward the vanishing point, clipped at y0
        t = (y1 - y0) / (y1 - vy)
        xt = x + (vx - x) * t
        out.append(f'<line x1="{x:.1f}" y1="{y1}" x2="{xt:.1f}" y2="{y0}"/>')
    for j in range(1, rows + 1):
        f = (j / rows) ** 2
        y = y0 + (y1 - y0) * f
        out.append(f'<line x1="{x0 - 200}" y1="{y:.1f}" x2="{x1 + 200}" y2="{y:.1f}"/>')
    return "\n".join(out)


# --------------------------------------------------------------------------- banner

def banner() -> str:
    W, H = 1280, 400
    ox, c = 778, 196
    scan_from, scan_to = ox - 40, ox + 500
    chips = [("blueprint", CY), ("program", "#9aa8ff"), ("manifold3d", "#7ee8ac"), ("build", AM)]
    chip_svg, x = [], 64
    for i, (t, col) in enumerate(chips):
        w = 18 + 8.2 * len(t)
        chip_svg.append(f'<rect x="{x}" y="296" width="{w:.0f}" height="26" rx="13" fill="{col}" fill-opacity=".12" stroke="{col}" stroke-opacity=".6"/>'
                        f'<text x="{x + w / 2:.1f}" y="313.5" text-anchor="middle" class="m" font-size="12.5" fill="{col}">{t}</text>')
        x += w
        if i < len(chips) - 1:
            chip_svg.append(f'<path d="M{x + 5},309 h14 m-5,-4 l5,4 l-5,4" fill="none" stroke="{DIM}" stroke-width="1.4"/>')
            x += 24
    labels = []
    for k, (name, x0, r0, x1, r1, col, _) in enumerate(PARTS):
        if k % 2:
            continue
        mx = ox + (x0 + x1) / 2
        ty = c - max(r0, r1) - 22
        labels.append(f'<line x1="{mx:.0f}" y1="{c - max(r0, r1) * .55:.0f}" x2="{mx:.0f}" y2="{ty + 6:.0f}" stroke="{col}" stroke-opacity=".7"/>'
                      f'<circle cx="{mx:.0f}" cy="{c - max(r0, r1) * .55:.0f}" r="2.5" fill="{col}"/>'
                      f'<rect x="{mx - 4 - 6.6 * len(name) / 2:.0f}" y="{ty - 12:.0f}" width="{8 + 6.6 * len(name):.0f}" height="19" rx="4" fill="#0b1420" stroke="{col}" stroke-opacity=".8"/>'
                      f'<text x="{mx:.0f}" y="{ty + 1:.0f}" text-anchor="middle" class="m" font-size="11" fill="{INK}">{name}</text>')
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">Replicator: you specify it, you build it</title>
<desc id="d">A night workshop floor. On the left, the Replicator title, the tagline, a specify prompt being typed and the pipeline blueprint, program, manifold3d, build. On the right a turbofan engine floats in an exploded view while a scan plane sweeps across it, turning the cyan blueprint wireframe into solid coloured parts: intake cowl, compressor, turbine stage and nozzle.</desc>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#05090f"/><stop offset=".62" stop-color="#0a1421"/><stop offset="1" stop-color="#0d1c2e"/></linearGradient>
<radialGradient id="halo" cx=".5" cy=".5" r=".5"><stop offset="0" stop-color="{CY}" stop-opacity=".22"/><stop offset="1" stop-color="{CY}" stop-opacity="0"/></radialGradient>
<linearGradient id="scan" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="{CY}" stop-opacity="0"/><stop offset=".85" stop-color="{CY}" stop-opacity=".35"/><stop offset="1" stop-color="#e9fbff" stop-opacity=".95"/></linearGradient>
<linearGradient id="floorfade" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/><stop offset=".5" stop-color="#fff" stop-opacity=".7"/><stop offset="1" stop-color="#fff" stop-opacity="1"/></linearGradient>
<mask id="fm"><rect x="0" y="250" width="{W}" height="150" fill="url(#floorfade)"/></mask>
<linearGradient id="fadeL" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="#05090f" stop-opacity="1"/><stop offset=".5" stop-color="#05090f" stop-opacity=".6"/><stop offset="1" stop-color="#05090f" stop-opacity="0"/></linearGradient>
<clipPath id="solid"><rect x="{scan_from}" y="0" width="{(scan_to - scan_from) * .55:.0f}" height="{H}">
  <animate attributeName="width" values="0;{scan_to - scan_from};{scan_to - scan_from};0" keyTimes="0;.45;.85;1" dur="9s" repeatCount="indefinite"/></rect></clipPath>
{shade_defs()}
<style>{STYLE}</style>
</defs>
<rect width="{W}" height="{H}" fill="url(#bg)"/>
<g stroke="{CY}" stroke-opacity=".16" stroke-width="1" mask="url(#fm)">{floor(560, 1300, 262, 400, 1010, 150, 26, 8)}</g>
<line x1="560" y1="262" x2="1280" y2="262" stroke="{CY}" stroke-opacity=".28"/>
<rect x="0" y="0" width="760" height="{H}" fill="url(#fadeL)"/>
<ellipse cx="1010" cy="300" rx="260" ry="26" fill="#000" fill-opacity=".45"/>
<ellipse cx="1010" cy="196" rx="300" ry="150" fill="url(#halo)"/>
<g class="float">
<g>{engine(ox, c, wire=True)}</g>
<g clip-path="url(#solid)">{engine(ox, c, wire=False)}</g>
<g>{"".join(labels)}</g>
<rect x="{scan_from - 60 + (scan_to - scan_from) * .55:.0f}" y="70" width="60" height="252" fill="url(#scan)">
  <animate attributeName="x" values="{scan_from - 60};{scan_to - 60};{scan_to - 60};{scan_from - 60}" keyTimes="0;.45;.85;1" dur="9s" repeatCount="indefinite"/></rect>
</g>
<text x="64" y="74" class="m" font-size="13" letter-spacing="3.2" fill="{AM}">ENGINEERING AND RESEARCH WORKSHOP</text>
<text x="62" y="138" class="s" font-size="62" font-weight="700" letter-spacing="1" fill="{INK}">Replicator</text>
<text x="64" y="178" class="s" font-size="22" fill="#c9d6e3">You specify it, you build it.</text>
<rect x="64" y="212" width="560" height="48" rx="24" fill="#0f1a28" stroke="#2a4e68" stroke-width="1.5"/>
<rect x="72" y="220" width="70" height="32" rx="16" fill="{CY}" fill-opacity=".14"/>
<text x="107" y="241" text-anchor="middle" class="m" font-size="12.5" font-weight="700" letter-spacing="2" fill="{CY}">SPECIFY</text>
<text x="156" y="241.5" class="s" font-size="15.5" fill="#d7e2ec">"a turbofan with reverse thrust doors"</text>
<rect x="433" y="227" width="2" height="19" fill="{CY}" class="blink"/>
<rect x="520" y="219" width="96" height="34" rx="17" fill="{BL}"/>
<text x="568" y="241" text-anchor="middle" class="s" font-size="14" font-weight="600" fill="#fff">Replicate</text>
{"".join(chip_svg)}
<text x="64" y="356" class="m" font-size="12" fill="{DIM}">your models · editable at every step · STEP / DXF / STL / 3MF / URDF · agents over MCP</text>
</svg>
"""


# --------------------------------------------------------------------------- how it works

def icon(kind: str, x: float, y: float, col: str) -> str:
    s = f'fill="none" stroke="{col}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
    if kind == "chat":
        return f'<path d="M{x},{y + 4}a5 5 0 0 1 5-5h20a5 5 0 0 1 5 5v12a5 5 0 0 1-5 5h-12l-7 6v-6h-1a5 5 0 0 1-5-5z" {s}/>'
    if kind == "sheet":
        return (f'<rect x="{x}" y="{y - 2}" width="28" height="30" rx="3" {s}/><path d="M{x + 6},{y + 6}h16M{x + 6},{y + 13}h16M{x + 6},{y + 20}h10" {s}/>')
    if kind == "code":
        return f'<path d="M{x + 8},{y + 3}l-8,10l8,10M{x + 22},{y + 3}l8,10l-8,10M{x + 18},{y}l-6,26" {s}/>'
    if kind == "cube":
        return (f'<path d="M{x + 15},{y - 2}l14,7v16l-14,7l-14-7v-16z M{x + 1},{y + 5}l14,7l14-7 M{x + 15},{y + 12}v16" {s}/>')
    if kind == "eye":
        return f'<path d="M{x},{y + 12}c8-12 24-12 32,0c-8,12-24,12-32,0z" {s}/><circle cx="{x + 16}" cy="{y + 12}" r="5" {s}/>'
    if kind == "image":
        return (f'<rect x="{x}" y="{y}" width="30" height="24" rx="4" {s}/><path d="M{x + 4},{y + 20}l7-8l6,6l4-4l8,6" {s}/>'
                f'<circle cx="{x + 22}" cy="{y + 7}" r="2.5" {s}/>')
    return ""


def how() -> str:
    W, H = 1200, 1000
    o = []
    o.append(f'<text x="40" y="52" class="m" font-size="13" letter-spacing="3" fill="{AM}">HOW REPLICATOR WORKS</text>')
    o.append(f'<text x="40" y="84" class="s" font-size="25" font-weight="600" fill="{INK}">A sentence goes in. An editable object comes out, one build step at a time.</text>')

    # ---- row 1: the pipeline
    o.append(f'<text x="40" y="132" class="m" font-size="12.5" letter-spacing="2.5" fill="{DIM}">THE PIPELINE</text>')
    stages = [
        ("chat", CY, "1 · Specify", ["A sentence, a sketch", "of an idea, or an edit"], '"a turbofan with', 'reverse doors"'),
        ("sheet", "#9aa8ff", "2 · Blueprint", ["Your model plans parts,", "sizes, materials"], "parts: 14", "units: mm"),
        ("code", "#c4a1ff", "3 · BuildProgram", ["Ordered ops, each tagged", "with its component"], "revolve · array", "boolean · loft"),
        ("cube", "#7ee8ac", "4 · Kernel", ["manifold3d evaluates", "every step, cached"], "10-60 ms", "watertight"),
        ("eye", AM, "5 · Workshop", ["Steps materialize on", "the floor, Qt Quick 3D"], "scrub · edit", "Qt Quick 3D"),
    ]
    bw, gap, y0 = 208, 15, 150
    for i, (ic, col, title, lines, k1, k2) in enumerate(stages):
        x = 40 + i * (bw + gap)
        o.append(f'<rect x="{x}" y="{y0}" width="{bw}" height="190" rx="12" fill="#0f1a28" stroke="{col}" stroke-opacity=".45" stroke-width="1.5"/>')
        o.append(f'<rect x="{x}" y="{y0}" width="{bw}" height="4" rx="2" fill="{col}"/>')
        o.append(icon(ic, x + 18, y0 + 24, col))
        o.append(f'<text x="{x + 62}" y="{y0 + 44}" class="s" font-size="16" font-weight="700" fill="{INK}">{title}</text>')
        for j, ln in enumerate(lines):
            o.append(f'<text x="{x + 18}" y="{y0 + 86 + j * 20}" class="s" font-size="13.5" fill="#c9d6e3">{ln}</text>')
        o.append(f'<rect x="{x + 14}" y="{y0 + 128}" width="{bw - 28}" height="48" rx="7" fill="#081220" stroke="{LINE}"/>')
        o.append(f'<text x="{x + 26}" y="{y0 + 148}" class="m" font-size="12" fill="{col}">{k1}</text>')
        o.append(f'<text x="{x + 26}" y="{y0 + 167}" class="m" font-size="12" fill="{col}">{k2}</text>')
        if i < len(stages) - 1:
            ax = x + bw
            o.append(f'<path class="flow" d="M{ax + 1},{y0 + 95} h{gap - 2}" stroke="{CY}" stroke-width="2"/>')
    # repair loop under 2->3
    x2 = 40 + 1 * (bw + gap) + bw / 2
    x3 = 40 + 2 * (bw + gap) + bw / 2
    x4 = 40 + 3 * (bw + gap) + bw / 2
    o.append(f'<path class="flow" d="M{x4},{y0 + 192} v24 H{x3 + 10} v-22" fill="none" stroke="#fb7185" stroke-width="1.8"/>')
    o.append(f'<path d="M{x3 + 5},{y0 + 200} l5,-7 l5,7" fill="none" stroke="#fb7185" stroke-width="1.8"/>')
    o.append(f'<text x="{(x3 + x4) / 2}" y="{y0 + 234}" text-anchor="middle" class="m" font-size="11.5" fill="#fb7185">validation errors go back to the model: repair rounds</text>')
    # edit loop 5 -> 3
    x5 = 40 + 4 * (bw + gap) + bw / 2
    o.append(f'<path class="flow" d="M{x5},{y0 - 2} v-10 H{x3 - 10} v8" fill="none" stroke="{AM}" stroke-width="1.8"/>')
    o.append(f'<path d="M{x3 - 15},{y0 - 9} l5,7 l5,-7" fill="none" stroke="{AM}" stroke-width="1.8"/>')
    o.append(f'<text x="{(x3 + x5) / 2 + 40}" y="{y0 - 18}" text-anchor="middle" class="m" font-size="11.5" fill="{AM}">"make the doors wider" becomes a JSON Patch on the program, saved as a new version</text>')

    # ---- row 2: modes
    y1 = 430
    o.append(f'<text x="40" y="{y1 - 18}" class="m" font-size="12.5" letter-spacing="2.5" fill="{DIM}">FIVE MODES, ONE SCENE</text>')
    modes = [
        ("Build", BL, "1", ["Play and scrub the build.", "Edit any step's params", "or placement; it rebuilds."]),
        ("Dissect", "#e06b7b", "2", ["Exploded along each part's", "own axis, with callouts", "that follow the parts."]),
        ("Reverse", "#7ee8ac", "3", ["Import any mesh: pieces,", "repeats, contacts, order,", "observed or inferred."]),
        ("Showcase", AM, "4", ["Stage and turntable.", "A Cycles still renders", "on the CPU."]),
        ("Present", "#c4a1ff", "5", ["Explain writes a checked", "account; Present walks", "it part by part."]),
    ]
    mw, mg = 210.3, 12.6
    for i, (name, col, key, lines) in enumerate(modes):
        x = 40 + i * (mw + mg)
        o.append(f'<rect x="{x}" y="{y1}" width="{mw}" height="132" rx="12" fill="#111b28" stroke="{LINE}"/>')
        o.append(f'<rect x="{x}" y="{y1}" width="4" height="132" rx="2" fill="{col}"/>')
        o.append(f'<text x="{x + 20}" y="{y1 + 32}" class="s" font-size="17" font-weight="700" fill="{col}">{name}</text>')
        o.append(f'<rect x="{x + mw - 44}" y="{y1 + 16}" width="22" height="22" rx="5" fill="none" stroke="{DIM}" stroke-opacity=".6"/>'
                 f'<text x="{x + mw - 33}" y="{y1 + 32}" text-anchor="middle" class="m" font-size="11" fill="{DIM}">{key}</text>')
        for j, ln in enumerate(lines):
            o.append(f'<text x="{x + 20}" y="{y1 + 62 + j * 20}" class="s" font-size="13.5" fill="#c9d6e3">{ln}</text>')

    # ---- row 3: in and out
    y2 = 620
    o.append(f'<text x="40" y="{y2 - 18}" class="m" font-size="12.5" letter-spacing="2.5" fill="{DIM}">IN AND OUT</text>')
    ins = [("image", "#c4a1ff", "Image to 3D", "a character sheet or any picture", "becomes a mesh in your ComfyUI"),
           ("cube", "#7ee8ac", "Mesh import", "GLB, STEP, OBJ, STL and 20 more formats", "open in Reverse and are taken apart")]
    outs = [("cube", AM, "Blender round trip", "Open in Blender, sculpt or texture,", "Pull back into Reverse (localhost:9876)"),
            ("sheet", CY, "Export", "STEP and DXF for CAD, GLB and OBJ,", "STL and 3MF to print, URDF and MJCF to simulate")]
    for col_i, group in enumerate((ins, outs)):
        for j, (ic, col, title, a, b) in enumerate(group):
            x = 40 if col_i == 0 else 640
            y = y2 + j * 84
            o.append(f'<rect x="{x}" y="{y}" width="520" height="72" rx="10" fill="#0f1a28" stroke="{LINE}"/>')
            o.append(icon(ic, x + 18, y + 22, col))
            o.append(f'<text x="{x + 66}" y="{y + 28}" class="s" font-size="15" font-weight="700" fill="{INK}">{title}</text>')
            o.append(f'<text x="{x + 66}" y="{y + 49}" class="s" font-size="13" fill="#c9d6e3">{a}</text>')
            o.append(f'<text x="{x + 66}" y="{y + 65}" class="s" font-size="13" fill="{DIM}">{b}</text>')
    # centre hub
    o.append(f'<circle cx="600" cy="{y2 + 78}" r="30" fill="#0b1420" stroke="{CY}" stroke-width="1.5" class="pulse"/>')
    o.append(f'<text x="600" y="{y2 + 83}" text-anchor="middle" class="m" font-size="11" fill="{CY}">scene</text>')
    for yy in (y2 + 36, y2 + 120):
        o.append(f'<path class="flow" d="M561,{yy} C580,{yy} 575,{y2 + 78} 570,{y2 + 78}" fill="none" stroke="{CY}" stroke-width="1.6"/>')
        o.append(f'<path class="flow" d="M630,{y2 + 78} C625,{y2 + 78} 620,{yy} 639,{yy}" fill="none" stroke="{CY}" stroke-width="1.6"/>')

    # ---- row 4: where the work runs
    y3 = 830
    o.append(f'<text x="40" y="{y3 - 18}" class="m" font-size="12.5" letter-spacing="2.5" fill="{DIM}">WHERE THE WORK RUNS</text>')
    o.append(f'<rect x="40" y="{y3}" width="1120" height="128" rx="12" fill="#0f1a28" stroke="{LINE}"/>')
    o.append(f'<rect x="64" y="{y3 + 24}" width="500" height="80" rx="9" fill="#0b1420" stroke="#7ee8ac" stroke-opacity=".6"/>')
    o.append(f'<text x="84" y="{y3 + 52}" class="m" font-size="14" font-weight="700" fill="#7ee8ac">Your machine</text>')
    o.append(f'<text x="84" y="{y3 + 74}" class="s" font-size="13.5" fill="#c9d6e3">Kernel, checks, mass, drawings and exports on the CPU.</text>')
    o.append(f'<text x="84" y="{y3 + 93}" class="s" font-size="12.5" fill="{DIM}">The window on any GPU; the iGPU when a model needs the big card.</text>')
    o.append(f'<rect x="596" y="{y3 + 24}" width="540" height="80" rx="9" fill="#0b1420" stroke="{AM}" stroke-opacity=".6"/>')
    o.append(f'<text x="616" y="{y3 + 52}" class="m" font-size="14" font-weight="700" fill="{AM}">Your model</text>')
    o.append(f'<text x="616" y="{y3 + 74}" class="s" font-size="13.5" fill="#c9d6e3">Any OpenAI-compatible endpoint: llama.cpp, Ollama, vLLM, hosted.</text>')
    o.append(f'<text x="616" y="{y3 + 93}" class="s" font-size="12.5" fill="{DIM}">Only the endpoints you name; keys stay in the environment.</text>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-labelledby="t d">
<title id="t">How Replicator works</title>
<desc id="d">Five stages: a sentence that specifies the object, a blueprint written by the model you choose, a BuildProgram of ordered operations, the manifold3d kernel that evaluates every step, and the workshop where the steps materialize. Validation errors loop back to the model for repair; edits in plain words become JSON Patches on the program. Five modes share one scene: Build, Dissect, Reverse, Showcase and Present. Image to 3D and mesh import come in; a Blender round trip and STEP, DXF, STL, 3MF, GLB, OBJ, URDF or MJCF export go out. Geometry, checks and exports run on your CPU; the model is any OpenAI-compatible endpoint you name.</desc>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0b1420"/><stop offset="1" stop-color="#070c13"/></linearGradient>
<style>{STYLE}</style>
</defs>
<rect width="{W}" height="{H}" rx="18" fill="url(#bg)"/>
<rect x=".75" y=".75" width="{W - 1.5}" height="{H - 1.5}" rx="17.5" fill="none" stroke="{LINE}" stroke-width="1.5"/>
{chr(10).join(o)}
</svg>
"""


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "banner.svg").write_text(banner())
    (ASSETS / "how-it-works.svg").write_text(how())
    print("wrote", ASSETS / "banner.svg", ASSETS / "how-it-works.svg")
