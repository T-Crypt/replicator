"""Studio: the one QObject QML talks to. Owns the program, the evaluator, the step cursor and the LLM jobs."""
from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from ..core import export as exporter
from ..core.evaluate import EvalError, Evaluator, bounds
from ..core.program import ProgramError, apply_patch, check, op_inputs
from ..llm import client
from .envmap import EnvMap
from .mesh_geometry import MeshGeometry

OUT = Path.home() / "Replicator"


class Studio(QObject):
    shapesChanged = Signal()
    programChanged = Signal()
    stepChanged = Signal()
    logChanged = Signal()
    busyChanged = Signal()
    selectionChanged = Signal()
    _jobDone = Signal(object, str)  # (program or None, message) from a worker thread

    def __init__(self):
        super().__init__()
        self._ev = Evaluator()
        self._program: dict | None = None
        self._history: list[dict] = []
        self._step = -1
        self._shapes: list[MeshGeometry] = []
        self._geo_cache: dict[str, MeshGeometry] = {}
        self._log: list[str] = []
        self._busy = ""
        self._engine = "dirk"
        self._selected = ""
        self._ground = 0.0
        self._radius = 300.0
        self._center_y = 150.0
        self._env = EnvMap()
        self._jobDone.connect(self._on_job)

    # ---------- properties ----------
    @Property("QVariantList", notify=shapesChanged)
    def shapes(self):
        return self._shapes

    @Property("QVariantList", notify=programChanged)
    def ops(self):
        if not self._program:
            return []
        consumed_at: dict[str, int] = {}
        for i, op in enumerate(self._program["ops"]):
            for ref in op_inputs(op):
                consumed_at.setdefault(ref, i)
        return [{"id": op["id"], "op": op["op"], "label": op.get("label", op["id"]),
                 "part": op.get("part", ""), "index": i, "consumedAt": consumed_at.get(op["id"], -1)}
                for i, op in enumerate(self._program["ops"])]

    @Property(str, notify=programChanged)
    def title(self):
        return (self._program or {}).get("name", "Untitled")

    @Property(str, notify=programChanged)
    def summary(self):
        bp = (self._program or {}).get("blueprint") or {}
        return bp.get("summary", "")

    @Property(int, notify=programChanged)
    def stepCount(self):
        return len(self._program["ops"]) if self._program else 0

    @Property(int, notify=stepChanged)
    def step(self):
        return self._step

    @Property(float, notify=shapesChanged)
    def ground(self):
        return self._ground

    @Property(float, notify=shapesChanged)
    def radius(self):
        return self._radius

    @Property(float, notify=shapesChanged)
    def centerY(self):
        return self._center_y

    @Property(QObject, constant=True)
    def envMap(self):
        return self._env

    @Property(str, notify=logChanged)
    def log(self):
        return "\n".join(self._log[-200:])

    @Property(str, notify=logChanged)
    def lastLog(self):
        return self._log[-1] if self._log else "Ready. Dream something."

    @Property(str, notify=busyChanged)
    def busy(self):
        return self._busy

    @Property(str, notify=selectionChanged)
    def selected(self):
        return self._selected

    @Property(str, notify=selectionChanged)
    def selectedJson(self):
        op = self._op(self._selected)
        return json.dumps(op, indent=1) if op else ""

    @Property("QVariantList", constant=True)
    def engines(self):
        return list(client.ENGINES)

    # ---------- helpers ----------
    def _say(self, msg: str):
        self._log.append(time.strftime("%H:%M:%S ") + msg)
        self.logChanged.emit()

    def _op(self, oid: str) -> dict | None:
        for op in (self._program or {}).get("ops", []):
            if op["id"] == oid:
                return op
        return None

    def _set_program(self, program: dict, note: str, keep_step: bool = False):
        check(program)
        if self._program is not None:
            self._history.append(self._program)
        self._program = program
        self.programChanged.emit()
        self._say(note)
        self.setStep(self.stepCount - 1 if keep_step else 0)

    def _rebuild(self):
        if not self._program:
            self._shapes = []
            self.shapesChanged.emit()
            return
        try:
            shapes = self._ev.step(self._program, self._step)
        except EvalError as e:
            self._say(f"build error: {e}")
            return
        mats = self._program.get("materials", {})
        lo, hi = bounds(self._ev.step(self._program))  # frame the finished build, not the partial one
        self._ground = -lo[1]
        ext = [hi[i] - lo[i] for i in range(3)]
        self._radius = max(0.5 * (ext[0] ** 2 + ext[1] ** 2 + ext[2] ** 2) ** 0.5, 1.0)  # bounding sphere
        self._center_y = ext[1] / 2
        prev = {s.hash for s in self._ev.step(self._program, self._step - 1)} if self._step > 0 else set()
        out = []
        for s in shapes:
            key = s.hash + "|" + json.dumps(mats.get(s.material), sort_keys=True)
            fresh = s.hash not in prev
            g = self._geo_cache.get(key)
            if g is None or g._fresh != fresh:
                g = MeshGeometry(s.id, s.label, s.part, mats.get(s.material), s.manifold, fresh)
                self._geo_cache[key] = g
            out.append(g)
        self._shapes = out
        self.shapesChanged.emit()

    # ---------- slots ----------
    @Slot(int)
    def setStep(self, k: int):
        if not self._program:
            return
        self._step = max(0, min(int(k), self.stepCount - 1))
        self.stepChanged.emit()
        self._rebuild()

    @Slot(str)
    def openFile(self, path: str):
        path = QUrl(path).toLocalFile() if path.startswith("file:") else path
        try:
            prog = json.loads(Path(path).read_text())
            self._history.clear()
            self._program = None
            self._set_program(prog, f"opened {Path(path).name}")
        except (OSError, json.JSONDecodeError, ProgramError) as e:
            self._say(f"open failed: {e}")

    @Slot(str)
    def setEngine(self, name: str):
        self._engine = name

    @Slot(str)
    def select(self, oid: str):
        self._selected = oid
        self.selectionChanged.emit()

    @Slot(str, result=bool)
    def applyOpJson(self, text: str) -> bool:
        try:
            new_op = json.loads(text)
            prog = copy.deepcopy(self._program)
            idx = next(i for i, op in enumerate(prog["ops"]) if op["id"] == self._selected)
            prog["ops"][idx] = new_op
            Evaluator().step(prog)
            self._set_program(prog, f"edited {new_op.get('id')}", keep_step=True)
            self.select(new_op.get("id", ""))
            return True
        except (StopIteration, json.JSONDecodeError, ProgramError, EvalError, TypeError) as e:
            self._say(f"edit rejected: {e}")
            return False

    @Slot()
    def undo(self):
        if not self._history:
            self._say("nothing to undo")
            return
        self._program = self._history.pop()
        self.programChanged.emit()
        self._say("undo")
        self.setStep(self.stepCount - 1)

    @Slot(str)
    def dream(self, text: str):
        self._run_job("Dreaming", lambda log: client.dream(text, self._engine, log=log))

    @Slot(str)
    def edit(self, text: str):
        if not self._program:
            return self.dream(text)
        base = copy.deepcopy(self._program)

        def job(log):
            patch = client.edit(base, text, self._engine, log=log)
            log(f"patch: {len(patch)} change(s)")
            return apply_patch(base, patch)
        self._run_job("Editing", job, keep_step=True)

    def _run_job(self, label: str, fn, keep_step: bool = False):
        if self._busy:
            self._say("busy: one model job at a time (one GPU)")
            return
        self._busy = f"{label} on {self._engine}"
        self.busyChanged.emit()
        self._keep = keep_step

        def run():
            try:
                prog = fn(lambda m: self._jobDone.emit(None, "log:" + m))
                self._jobDone.emit(prog, "done")
            except Exception as e:  # noqa: BLE001 - every failure is reported in the console
                self._jobDone.emit(None, f"failed: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _on_job(self, prog, msg: str):
        if msg.startswith("log:"):
            self._say(msg[4:])
            return
        self._busy = ""
        self.busyChanged.emit()
        if prog is None:
            self._say(msg)
            return
        OUT.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        (OUT / f"{stamp}.json").write_text(json.dumps(prog, indent=1))
        self._set_program(prog, f"built: {prog.get('name', '')} ({len(prog['ops'])} steps), saved {stamp}.json",
                          keep_step=self._keep)

    @Slot(str, result=str)
    def exportAs(self, fmt: str) -> str:
        if not self._program:
            return ""
        OUT.mkdir(parents=True, exist_ok=True)
        name = "".join(c if c.isalnum() else "-" for c in self.title.lower()).strip("-") or "build"
        path = OUT / f"{name}.{fmt}"
        try:
            exporter.export(self._ev.step(self._program), self._program.get("materials", {}), path)
            self._say(f"exported {path}")
            return str(path)
        except (ValueError, EvalError) as e:
            self._say(f"export failed: {e}")
            return ""
