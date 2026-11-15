"""Replicator - you specify it, you build it.

    python -m replicator.app [program.json] [--software] [--shot out.png --step N]

The GPU policy is applied before Qt is imported (replicator.gpu): on a machine with an Intel iGPU beside an NVIDIA
card the window draws on the iGPU and leaves the card to the model server. --software uses llvmpipe (test harness). --shot renders one frame to a PNG and exits (headless checks).
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
    ap.add_argument("--record", help="record frames to this folder in real time; needs --cues. Run it through "
                    "tools/record.sh (a headless gamescope): the window must be exposed to be grabbed twice")
    ap.add_argument("--cues", help='JSON list of [seconds, "QML expression"] played while recording; ["end", t] stops')
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--step", type=int, default=-1)
    ap.add_argument("--blueprint", type=float, default=0.0)
    ap.add_argument("--mode", default="", help="build | dissect | reverse | showcase | present (for --shot)")
    ap.add_argument("--explode", type=float, default=-1.0)
    ap.add_argument("--select", default="")
    ap.add_argument("--size", default="", help="WxH window size for --shot")
    ap.add_argument("--theme", default="", help="abyss | graphite | carbon | daylight (this run only with --shot)")
    ap.add_argument("--accent", default="", help="holo | azure | violet | mint | amber | rose")
    ap.add_argument("--density", default="", help="compact | cozy | roomy")
    ap.add_argument("--ui", default="", help="open an overlay for --shot: commander | preferences | materials | console | context | sheet")
    a = ap.parse_args(argv)

    pinned = gpu.apply(software=a.software)

    from PySide6.QtCore import QTimer
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick3D import QQuick3D
    from PySide6.QtQuickControls2 import QQuickStyle

    from .qt.bridge import Studio

    QGuiApplication.setApplicationName("Replicator")
    QGuiApplication.setOrganizationName("Replicator")       # preferences: ~/.config/Replicator/Replicator.conf
    QGuiApplication.setOrganizationDomain("replicator.local")
    QGuiApplication.setDesktopFileName("replicator")
    app = QGuiApplication(sys.argv[:1])
    if a.shot or a.record:  # a headless frame never reads or writes the operator's preferences
        import tempfile
        from PySide6.QtCore import QSettings
        QSettings.setPath(QSettings.Format.NativeFormat, QSettings.Scope.UserScope, tempfile.mkdtemp(prefix="replicator-shot-"))
    from PySide6.QtGui import QFont, QFontDatabase
    if "Inter" in QFontDatabase.families():
        f = QFont("Inter")
        f.setPixelSize(12)
        app.setFont(f)
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
    engine.rootContext().setContextProperty("boot", {"theme": a.theme, "accent": a.accent, "density": a.density,
                                                     "ui": a.ui, "shot": bool(a.shot or a.record)})
    engine.addImportPath(str(ROOT / "qml"))                 # the Replicator.UI module
    if a.shot:  # never shown: grabWindow renders a non-exposed window offscreen (once; a second grab crashes Qt)
        engine.setInitialProperties({"visible": False})
    engine.load(str(ROOT / "qml" / "Main.qml"))
    if not engine.rootObjects():
        print("QML failed to load", file=sys.stderr)
        return 2
    win = engine.rootObjects()[0]

    if a.program:
        studio.openFile(a.program)
        if a.step >= 0 or a.shot or a.record:
            studio.setStep(a.step if a.step >= 0 else studio.stepCount - 1)
        elif not (a.shot or a.record):
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
    if a.ui == "sheet":
        studio.makeSheet("blueprint")
    if a.blueprint:
        win.setProperty("blueprint", a.blueprint)
    if a.explode >= 0:
        win.setProperty("explodeTarget", a.explode)

    def self_check():
        if gpu.on_nvidia():
            print("Replicator landed on the NVIDIA card despite the iGPU pin; quitting so the model server keeps it "
                  "(set REPLICATOR_GPU=any to allow it)", file=sys.stderr)
            app.exit(3)
    if pinned:
        QTimer.singleShot(4000, self_check)

    if a.record:
        return _record(app, win, studio, a)
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


def _record(app, win, studio, a) -> int:
    """Grab the hidden window in real time while the cues play. Each frame's real timestamp goes to frames.txt as an
    ffmpeg concat list, so the film keeps true speed even when a frame takes longer than 1/fps to draw."""
    import json
    import time
    from pathlib import Path
    from PySide6.QtCore import QMetaObject, QTimer, Q_ARG
    out = Path(a.record)
    out.mkdir(parents=True, exist_ok=True)
    cues = json.loads(Path(a.cues).read_text())
    end = next(float(c[1]) for c in cues if c[0] == "end")
    plays = sorted(([float(t), js] for t, js in cues if t != "end"), key=lambda c: c[0])
    st = {"t0": None, "i": 0, "frames": []}

    def tick():
        now = time.perf_counter()
        if st["t0"] is None:
            st["t0"] = now
        t = now - st["t0"]
        while plays and plays[0][0] <= t:
            _, js = plays.pop(0)
            try:
                QMetaObject.invokeMethod(win, "runCue", Q_ARG("QVariant", js))
            except Exception as e:  # noqa: BLE001 - a bad cue is reported, the take goes on
                print(f"cue failed at {t:.2f} s: {js}: {e}", file=sys.stderr)
        img = win.grabWindow()
        name = f"{st['i']:05d}.jpg"
        img.save(str(out / name), "JPG", 95)
        st["frames"].append((name, t))
        st["i"] += 1
        if t >= end:
            lines = ["ffconcat version 1.0"]
            for (n, t0), (_, t1) in zip(st["frames"], st["frames"][1:] + [(None, t + 1 / a.fps)]):
                lines += [f"file {n}", f"duration {max(t1 - t0, 0.001):.4f}"]
            (out / "frames.txt").write_text("\n".join(lines) + "\n")
            dt = [b - a_ for (_, a_), (_, b) in zip(st["frames"], st["frames"][1:])]
            print(f"recorded {len(st['frames'])} frames over {t:.1f} s, mean {1 / (sum(dt) / len(dt)):.1f} fps, "
                  f"worst gap {max(dt) * 1000:.0f} ms -> {out}")
            app.exit(0)
            return
        QTimer.singleShot(max(1, int(1000 / a.fps - (time.perf_counter() - now) * 1000)), tick)

    QTimer.singleShot(int(os.environ.get("REPLICATOR_SHOT_MS", "3500")), tick)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
