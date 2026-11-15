"""A drawing sheet on disk: the SVG from core.drawing, plus a PNG that Qt renders from it."""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from ..core import assembly, drawing
from ..core.evaluate import Evaluator
from ..core.program import check


def render_png(svg: str, png: Path, dpi: int = 150) -> Path:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QGuiApplication

    from .svg import render_png as qt_render
    QGuiApplication.instance() or QGuiApplication([])
    return qt_render(svg, png, drawing.SHEET, dpi)


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
