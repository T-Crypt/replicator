"""SVG to PNG with QtSvg (the blueprint sheets). Safe off the GUI thread: it paints into a QImage, not a window."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QFontDatabase, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

_FAMILY = re.compile(r'font-family="([^"]*)"')


def _one_family(css: str) -> str:
    """QtSvg reads a CSS family list as one name and falls back; hand it the first installed family instead."""
    names = [n.strip().strip("'\"") for n in css.split(",")]
    have = set(QFontDatabase.families())
    for n in names:
        if n in have:
            return n
    mono = "monospace" in names and "sans-serif" not in names
    system = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont if mono else QFontDatabase.SystemFont.GeneralFont).family()
    if system in have:
        return system
    # fontconfig can name a system font that is not installed (an alias such as Noto Sans); take a real one
    kind = "Mono" if mono else "Sans"
    return next((f for f in sorted(have) if kind in f and (mono or "Mono" not in f)), min(have, default=system))


def render_png(svg: str, png: Path, size_mm: tuple[float, float], dpi: int = 150) -> Path:
    svg = _FAMILY.sub(lambda m: f'font-family="{_one_family(m.group(1))}"', svg)
    w, h = (round(v / 25.4 * dpi) for v in size_mm)
    img = QImage(w, h, QImage.Format.Format_RGB32)
    img.fill(0xFFFFFF)
    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode())).render(painter)
    painter.end()
    if not img.save(str(png)):
        raise OSError(f"could not write {png}")
    return png
