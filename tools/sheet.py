"""Draw a blueprint sheet for a BuildProgram: SVG, plus a PNG rendered by Qt.

    .venv/bin/python -m tools.sheet path/to/program.json [--style blueprint|paper] [--out out/sheet] [--dpi 150]
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from replicator.core import assembly, drawing
from replicator.core.evaluate import Evaluator
from replicator.core.program import check


def render_png(svg: str, png: Path, dpi: int = 150) -> Path:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QByteArray
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer
    QGuiApplication.instance() or QGuiApplication([])
    w, h = (round(v / 25.4 * dpi) for v in drawing.SHEET)
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFF)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    img.save(str(png))
    return png


def make(program_path: Path, out: Path, style: str = "blueprint", dpi: int = 150) -> tuple[Path, Path, float]:
    program = check(json.loads(program_path.read_text()))
    t0 = time.perf_counter()
    shapes = Evaluator(program_path.parent).step(program)
    svg = drawing.sheet_svg(program, shapes, assembly.components(program, shapes), style,
                            source="Replicator · " + program_path.name)
    seconds = time.perf_counter() - t0
    out.mkdir(parents=True, exist_ok=True)
    svg_path = out / f"{program_path.stem}.svg"
    svg_path.write_text(svg)
    return svg_path, render_png(svg, out / f"{program_path.stem}.png", dpi), seconds


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
