"""Draw a blueprint sheet for a BuildProgram: SVG, plus a PNG rendered by Qt.

    .venv/bin/python -m tools.sheet path/to/program.json [--style blueprint|paper] [--out out/sheet] [--dpi 150]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from replicator.core import drawing
from replicator.qt.drawing_sheet import make

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("program", nargs="+", type=Path)
    ap.add_argument("--style", default="blueprint", choices=sorted(drawing.STYLES))
    ap.add_argument("--out", type=Path, default=Path("out/sheet"))
    ap.add_argument("--dpi", type=int, default=150)
    a = ap.parse_args()
    for p in a.program:
        svg, png, sec = make(p, a.out, a.style, a.dpi)
        print(f"{p}: {png} ({sec:.1f} s)")
