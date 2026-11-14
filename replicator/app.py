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
    ap.add_argument("--mode", default="", help="build | dissect | reverse | showcase (for --shot)")
    ap.add_argument("--explode", type=float, default=-1.0)
    ap.add_argument("--select", default="")
    ap.add_argument("--size", default="", help="WxH window size for --shot")
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
    from PySide6.QtGui import QColor, QPalette
    pal = QPalette()
    for role, c in ((QPalette.Window, "#26282c"), (QPalette.WindowText, "#d9dce1"), (QPalette.Base, "#1a1b1e"),
                    (QPalette.AlternateBase, "#2d3035"), (QPalette.Text, "#d9dce1"), (QPalette.Button, "#2d3035"),
                    (QPalette.ButtonText, "#d9dce1"), (QPalette.Highlight, "#3d8ee6"), (QPalette.HighlightedText, "#ffffff"),
                    (QPalette.ToolTipBase, "#1a1b1e"), (QPalette.ToolTipText, "#d9dce1"), (QPalette.PlaceholderText, "#5c616a"),
                    (QPalette.Mid, "#3a3d43"), (QPalette.Dark, "#1c1d20"), (QPalette.Light, "#3a3d43")):
        pal.setColor(role, QColor(c))
    app.setPalette(pal)

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
    if a.size:
        w, h = (int(x) for x in a.size.split("x"))
        win.setProperty("width", w)
        win.setProperty("height", h)
    if a.mode:
        from PySide6.QtCore import QMetaObject, Q_ARG
        QMetaObject.invokeMethod(win, "setMode", Q_ARG("QVariant", a.mode))
    if a.select:
        studio.select(a.select)
    if a.blueprint:
        win.setProperty("blueprint", a.blueprint)
    if a.explode >= 0:
        win.setProperty("explodeTarget", a.explode)

    def self_check():
        if gpu.on_nvidia():
            print("Replicator reached the RTX card; quitting (the 4090 is llama-swap's)", file=sys.stderr)
            app.exit(3)
    QTimer.singleShot(4000, self_check)

    if a.shot:
        state = {"waited": 0, "settled": False}

        def grab():
            if studio.busy and state["waited"] < 180_000:  # an import or render job is still running
                state["waited"] += 500
                QTimer.singleShot(500, grab)
                return
            if state["waited"] and not state["settled"]:  # let the new scene materialize after the job lands
                state["settled"] = True
                QTimer.singleShot(3000, grab)
                return
            img = win.grabWindow()
            img.save(a.shot)
            print("saved", a.shot, img.width(), img.height())
            app.exit(0)
        QTimer.singleShot(int(os.environ.get("REPLICATOR_SHOT_MS", "3500")), grab)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
