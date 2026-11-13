"""Replicator - you dream it, you build it.

    python -m replicator.app [program.json] [--software] [--shot out.png --step N]

The GPU pin is applied before Qt is imported (replicator.gpu), so the window draws on the Intel iGPU and never
on the 4090. After the first frame the app checks nvidia-smi for its own PID and quits if it is there.
--software uses llvmpipe (test harness). --shot renders one frame to a PNG and exits (headless checks).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import gpu

ROOT = Path(__file__).resolve().parent.parent


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="replicator")
    ap.add_argument("program", nargs="?")
    ap.add_argument("--software", action="store_true")
    ap.add_argument("--shot")
    ap.add_argument("--step", type=int, default=-1)
    ap.add_argument("--blueprint", type=float, default=0.0)
    a = ap.parse_args(argv)

    gpu.apply(software=a.software)

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick3D import QQuick3D
    from PySide6.QtQuickControls2 import QQuickStyle

    from .qt.bridge import Studio

    QGuiApplication.setApplicationName("Replicator")
    QGuiApplication.setDesktopFileName("replicator")
    app = QGuiApplication(sys.argv[:1])
    from PySide6.QtGui import QSurfaceFormat
    QSurfaceFormat.setDefaultFormat(QQuick3D.idealSurfaceFormat(4))  # needs the app; before any window
    QQuickStyle.setStyle("Fusion")

    studio = Studio()
    engine = QQmlApplicationEngine()
    engine.warnings.connect(lambda ws: [print("QML:", w.toString(), file=sys.stderr) for w in ws])
    engine.rootContext().setContextProperty("studio", studio)
    if a.shot:  # never shown: grabWindow renders a non-exposed window offscreen
        engine.setInitialProperties({"visible": False})
    engine.load(str(ROOT / "qml" / "Main.qml"))
    if not engine.rootObjects():
        print("QML failed to load", file=sys.stderr)
        return 2
    win = engine.rootObjects()[0]

    if a.program:
        studio.openFile(a.program)
        if a.step >= 0 or a.shot:
            studio.setStep(a.step if a.step >= 0 else studio.stepCount - 1)
        elif not a.shot:
            win.setProperty("playing", True)
    if a.blueprint:
        bp = win.findChild(object, "bpSlider")
        if bp is not None:
            bp.setProperty("value", a.blueprint)

    def self_check():
        if gpu.on_nvidia():
            print("Replicator reached the RTX card; quitting (the 4090 is llama-swap's)", file=sys.stderr)
            app.exit(3)
    QTimer.singleShot(4000, self_check)

    if a.shot:
        def grab():
            img = win.grabWindow()
            img.save(a.shot)
            print("saved", a.shot, img.width(), img.height())
            app.exit(0)
        QTimer.singleShot(int(os.environ.get("REPLICATOR_SHOT_MS", "3500")), grab)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
