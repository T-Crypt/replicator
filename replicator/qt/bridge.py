"""Studio: the one QObject QML talks to. Owns the program, evaluator, timeline cursor, modes, components, the
reverse-engineering ledger, and the model / render jobs."""
from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QCoreApplication, QObject, QFileSystemWatcher, QTimer, QUrl, Signal, Slot

from .. import config, voice
from ..core import assembly, critique, drawing, explain, importers, materials, physics, reverse
from ..core import export as exporter
from ..core.evaluate import EvalError, Evaluator, RawMesh, bounds
from ..core.ops_engineering import HOLES
from ..core.program import (ProgramError, apply_patch, check, component_map, component_ops,
                             delete_component, duplicate_component, op_inputs, scale_program)
from ..image3d import pipeline, sheet
from ..llm import client
from . import library
from .envmap import EnvMap
from .mesh_geometry import MeshGeometry

OUT = Path.home() / "Replicator"
HISTORY_LIMIT = 200
GEO_CACHE_LIMIT = 600      # viewport meshes kept for instant undo and scrub
EVAL_CACHE_LIMIT = 4000    # kernel results kept (op hash -> solid)
MODES = ("build", "dissect", "reverse", "showcase", "present")
ENUMS = {"mode": {"boolean": ["union", "difference", "intersection"], "array": ["linear", "radial", "mirror"],
                  "deform": ["taper", "twist", "bend"]},
         "axis": ["x", "y", "z"], "hole": list(HOLES)}
INT_PARAMS = {"count", "teeth", "turns", "segments", "levels", "blades", "smooth"}
MEASURE_DELAY_MS = 150     # critique and mass wait for edits to settle, then run off the GUI thread


def _local(path: str) -> Path:
    return Path(QUrl(path).toLocalFile() if path.startswith("file:") else path).expanduser()


class Studio(QObject):
    shapesChanged = Signal()
    programChanged = Signal()
    stepChanged = Signal()
    logChanged = Signal()
    busyChanged = Signal()
    selectionChanged = Signal()
    modeChanged = Signal()
    reportChanged = Signal()
    renderChanged = Signal()
    sheetChanged = Signal()
    holodeckChanged = Signal()
    historyChanged = Signal()
    libraryChanged = Signal()
    explanationChanged = Signal()
    issuesChanged = Signal()
    factsChanged = Signal()
    measuringChanged = Signal()
    _measured = Signal(object, object, object)
    servicesChanged = Signal()
    voiceChanged = Signal()
    dictated = Signal(str)
    _voiceEvent = Signal(str, str)
    _jobDone = Signal(object, str)

    def __init__(self):
        super().__init__()
        self._ev = Evaluator()
        self._program: dict | None = None
        self._project: Path | None = None
        self._history: list[dict] = []
        self._future: list[dict] = []
        self._stats: dict = {}
        self._ops_rows: list | None = None
        self._comp_rows: list | None = None
        self._step = -1
        self._shapes: list[MeshGeometry] = []
        self._prev_shapes: list = []
        self._geo_cache: dict[str, MeshGeometry] = {}
        self._comps: list[assembly.Component] = []
        self._log: list[str] = []
        self._busy = ""
        self._engine = "dirk"
        self._selected = ""
        self._mode = "build"
        self._mode_after: str | None = None
        self._report: dict = {}
        self._render_path = ""
        self._sheet: dict = {}
        self._ground = 0.0
        self._radius = 300.0
        self._center = [0.0, 150.0, 0.0]
        self._env = EnvMap()
        self._holodeck_watcher = QFileSystemWatcher()
        if sheet.CHARACTERS.is_dir():
            self._holodeck_watcher.addPath(str(sheet.CHARACTERS))
            self._holodeck_watcher.directoryChanged.connect(self.holodeckChanged.emit)
        self._jobDone.connect(self._on_job)
        self._measured.connect(self._on_measured)
        self.selectionChanged.connect(self.factsChanged)
        self.shapesChanged.connect(self.factsChanged)
        self.issuesChanged.connect(self.factsChanged)
        self._measure_timer = QTimer(self)
        self._measure_timer.setSingleShot(True)
        self._measure_timer.setInterval(MEASURE_DELAY_MS)
        self._measure_timer.timeout.connect(self._start_measure)
        self._measure_job = None
        self._measure_thread: threading.Thread | None = None
        self._measuring = False
        self._cfg = config.load()
        self._explanation: dict = {}
        self._issues: list[dict] = []
        self._issues_of: dict | None = None
        self._epoch = 0
        self._mass: physics.Mass | None = None
        self._rest = "flush"
        self._say_token = 0
        self._player = None
        self._speaking = False
        self._rec = None
        self._listening = False
        self._voiceEvent.connect(self._on_voice)

    # ------------------------------------------------------------------ properties
    @Property("QVariantList", notify=shapesChanged)
    def shapes(self):
        return self._shapes

    @Property("QVariantList", notify=shapesChanged)
    def ops(self):
        if not self._program:
            return []
        if self._ops_rows is not None:
            return self._ops_rows
        comp = component_map(self._program)
        colors = {c.id: c.color for c in self._comps}
        consumed_at: dict[str, int] = {}
        for i, op in enumerate(self._program["ops"]):
            for ref in op_inputs(op):
                consumed_at.setdefault(ref, i)
        self._ops_rows = [
            {"id": op["id"], "op": op["op"], "label": op.get("label", op["id"]), "part": op.get("part", ""),
             "component": comp[op["id"]], "color": colors.get(comp[op["id"]], "#8a8f98"), "index": i,
             "consumedAt": consumed_at.get(op["id"], -1)}
            for i, op in enumerate(self._program["ops"])]
        return self._ops_rows

    @Property("QVariantList", notify=shapesChanged)
    def components(self):
        if self._comp_rows is not None:
            return self._comp_rows
        g = self._ground
        self._comp_rows = [{"id": c.id, "label": c.label, "role": c.role, "color": c.color, "count": len(c.shapes),
                 "order": c.order, "shapes": c.shapes,
                 "center": [float(c.center[0]), float(c.center[1]) + g, float(c.center[2])],
                 "offset": [float(x) for x in (c.offset if c.offset is not None else [0, 0, 0])],
                 "size": [float(x) for x in (c.hi - c.lo)]} for c in self._comps]
        return self._comp_rows

    @Property(str, notify=programChanged)
    def title(self):
        return (self._program or {}).get("name", "Untitled")

    @Property(str, notify=programChanged)
    def summary(self):
        return ((self._program or {}).get("blueprint") or {}).get("summary", "")

    @Property("QVariantList", notify=shapesChanged)
    def dimensions(self):
        return self._dims

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

    @Property("QVariantList", notify=shapesChanged)
    def center(self):
        return self._center

    @Property(QObject, constant=True)
    def envMap(self):
        return self._env

    @Property(str, notify=logChanged)
    def log(self):
        return "\n".join(self._log[-300:])

    @Property(str, notify=logChanged)
    def lastLog(self):
        return self._log[-1] if self._log else "Ready. Specify something, or import a model to take apart."

    @Property(str, notify=busyChanged)
    def busy(self):
        return self._busy

    @Property(str, notify=modeChanged)
    def mode(self):
        return self._mode

    @Property(str, notify=selectionChanged)
    def selected(self):
        return self._selected

    @Property(str, notify=selectionChanged)
    def selectedComponent(self):
        for g in self._shapes:
            if g.shapeId == self._selected:
                return g.component
        return self._selected if any(c.id == self._selected for c in self._comps) else ""

    @Property(str, notify=selectionChanged)
    def selectedJson(self):
        op = self._op(self._selected)
        return json.dumps(op, indent=1) if op else ""

    @Property(str, notify=selectionChanged)
    def selectedOpKind(self):
        op = self._op(self._selected)
        return op["op"] if op else ""

    @Property("QVariantList", notify=selectionChanged)
    def selectedParams(self):
        """Typed rows for the Attribute Manager: number, vec3, enum, bool, text or json (point lists)."""
        op = self._op(self._selected)
        if not op:
            return []
        rows = [{"key": "label", "kind": "text", "value": op.get("label", "")},
                {"key": "material", "kind": "enum", "value": op.get("material") or "",
                 "options": [""] + sorted((self._program or {}).get("materials", {}))}]
        params = op.get("params", {})
        for k, v in params.items():
            if k in ("translate", "rotate", "scale"):
                continue
            if isinstance(v, bool):
                rows.append({"key": k, "kind": "bool", "value": v})
            elif isinstance(v, (int, float)):
                whole = k in INT_PARAMS
                rows.append({"key": k, "kind": "number", "value": float(v), "integer": whole,
                             "step": 1.0 if whole else max(abs(float(v)) * 0.01, 0.1)})
            elif k in ENUMS and isinstance(v, str):
                opts = ENUMS[k] if isinstance(ENUMS[k], list) else ENUMS[k].get(op["op"], [v])
                rows.append({"key": k, "kind": "enum", "value": v, "options": opts})
            elif isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v):
                rows.append({"key": k, "kind": "vec3", "value": [float(x) for x in v]})
            else:
                rows.append({"key": k, "kind": "json", "value": json.dumps(v)})
        if op["op"] == "grille" and "hole" not in params:
            rows.append({"key": "hole", "kind": "enum", "value": "hex", "options": list(HOLES)})
        for k in ("translate", "rotate", "scale"):
            v = params.get(k)
            if isinstance(v, (int, float)):
                v = [float(v)] * 3
            rows.append({"key": k, "kind": "vec3", "group": "Coordinates",
                         "value": [float(x) for x in v] if v else ([1.0] * 3 if k == "scale" else [0.0] * 3)})
        return rows

    @Property("QVariantMap", notify=factsChanged)
    def selectedFacts(self):
        """Measured facts for the selection: size (mm) of the part or component, and its component's mass (kg)."""
        if not self._program or not self._selected:
            return {}
        comp = self.selectedComponent
        try:
            full = self._ev.step(self._program)
        except EvalError:
            return {}
        parts = [s for s in full if s.id == self._selected] or [s for s in full if s.component == comp]
        out: dict = {"component": comp}
        if parts:
            lo, hi = bounds(parts)
            out["size"] = [round(float(hi[i] - lo[i]), 1) for i in range(3)]
        kg = (self._mass.by_component.get(comp) if self._mass else None)
        if kg is not None:
            out["kg"] = float(kg)
        return out

    @Property(str, constant=True)
    def importPatterns(self):
        return importers.patterns()

    @Property("QVariantList", constant=True)
    def engines(self):
        return list(client.ENGINES)

    @Property("QVariantList", notify=reportChanged)
    def ledger(self):
        return self._report.get("ledger", [])

    @Property("QVariantList", notify=reportChanged)
    def checklist(self):
        return self._report.get("checklist", [])

    @Property("QVariantMap", notify=reportChanged)
    def reportInput(self):
        return self._report.get("input", {})

    @Property("QVariantMap", notify=sheetChanged)
    def sheet(self):
        """The last blueprint sheet: {png, svg, seconds}; empty when none is open."""
        return self._sheet

    @Slot()
    def closeSheet(self):
        if self._sheet:
            self._sheet = {}
            self.sheetChanged.emit()

    @Slot(str)
    def makeSheet(self, style: str):
        """A dimensioned A3 blueprint sheet of the finished build (SVG plus PNG), drawn off the GUI thread."""
        if not self._program:
            return
        if self._busy:
            return self._say("busy: one job at a time (one GPU)")
        from .svg import render_png
        prog, shapes = self._program, self._ev.step(self._program)
        comps = assembly.components(prog, shapes)
        name = "".join(c if c.isalnum() else "-" for c in self.title.lower()).strip("-") or "build"
        work = OUT / "sheets"
        source = f"Replicator · {self._engine}"

        def job(log):
            t = time.time()
            svg = drawing.sheet_svg(prog, shapes, comps, style if style in drawing.STYLES else "blueprint", source)
            work.mkdir(parents=True, exist_ok=True)
            stem = work / f"{name}-{time.strftime('%Y%m%d-%H%M%S')}"
            stem.with_suffix(".svg").write_text(svg)
            png = render_png(svg, stem.with_suffix(".png"), drawing.SHEET, 150)
            return {"sheet": {"png": str(png), "svg": str(stem.with_suffix(".svg")),
                              "seconds": round(time.time() - t, 1)}}
        self._run_job("Drawing the blueprint sheet", job)

    @Property(str, notify=renderChanged)
    def renderPath(self):
        return self._render_path

    @Property("QVariantList", notify=holodeckChanged)
    def holodeckSheets(self):
        """Holodeck character sheets, newest first."""
        rows = []
        if sheet.CHARACTERS.is_dir():
            for p in sheet.CHARACTERS.glob("*.png"):
                rows.append({"path": str(p), "name": p.stem, "subject": sheet.subject(sheet.sidecar(p)),
                             "mtime": p.stat().st_mtime})
        rows.sort(key=lambda r: -r["mtime"])
        return rows

    @Property("QVariantMap", notify=shapesChanged)
    def stats(self):
        """Kernel read-outs for the status bar: triangles, parts, build time and cache use of the last rebuild."""
        return self._stats

    @Property(bool, notify=historyChanged)
    def canUndo(self):
        return bool(self._history)

    @Property(bool, notify=historyChanged)
    def canRedo(self):
        return bool(self._future)

    @Property("QVariantList", constant=True)
    def materialLibrary(self):
        return materials.rows()

    @Property("QVariantList", notify=programChanged)
    def programMaterials(self):
        return materials.program_rows(self._program)

    @Property(str, notify=selectionChanged)
    def selectedMaterial(self):
        if not self._program:
            return ""
        for g in self._shapes:
            if g.shapeId == self._selected:
                return g.materialName
        op = self._op(self._selected)
        return (op or {}).get("material") or ""

    @Property(bool, notify=measuringChanged)
    def measuring(self):
        return self._measuring

    @Property("QVariantList", notify=issuesChanged)
    def issues(self):
        return self._issues

    @Property("QVariantMap", notify=issuesChanged)
    def mass(self):
        """Computed mass properties: kg, centre of gravity, per component, and which parts use an assumed density."""
        m = self._mass
        if m is None:
            return {}
        return {"kg": m.kg, "cg": m.cg, "byComponent": m.by_component, "assumed": len(m.assumed), "stands": m.stands}

    @Property("QVariantMap", notify=explanationChanged)
    def explanation(self):
        """The checked explanation of the open object ({} until Explain has run): chapters, sources, notice."""
        return self._explanation

    @Property(str, notify=modeChanged)
    def restPose(self):
        """'flush' or 'levitate': how Present shows the object (measured from its footprint)."""
        return self._rest

    @Property("QVariantMap", notify=servicesChanged)
    def services(self):
        """Optional services (web research, voice) and what is usable right now."""
        return {**self._cfg, "status": voice.status(self._cfg)}

    @Property(bool, notify=voiceChanged)
    def speaking(self):
        return self._speaking

    @Property(bool, notify=voiceChanged)
    def listening(self):
        return self._listening

    @Property("QVariantList", notify=libraryChanged)
    def examples(self):
        return library.examples()

    @Property("QVariantList", notify=libraryChanged)
    def recents(self):
        return library.recents(OUT)

    @Property("QVariantList", notify=programChanged)
    def reference(self):
        """Reference images of the open program (image to 3D keeps the views it was built from): key, label, path."""
        ref = (self._program or {}).get("reference") or {}
        out = []
        for v in ref.get("views", []):
            p = Path(v.get("image", ""))
            if not p.is_absolute() and self._project:
                p = self._project / p
            p = p.resolve()
            if p.is_file():
                fill, cy = library.figure_extent(p)
                out.append({"key": v.get("key", "front"), "label": v.get("label", v.get("key", "")), "path": str(p),
                            "fill": fill, "cy": cy})
        return out

    # ------------------------------------------------------------------ helpers
    _dims: list = []

    def _say(self, msg: str):
        self._log.append(time.strftime("%H:%M:%S ") + msg)
        self.logChanged.emit()

    def _op(self, oid: str) -> dict | None:
        for op in (self._program or {}).get("ops", []):
            if op["id"] == oid:
                return op
        return None

    def _set_program(self, program: dict, note: str, keep_step: bool = False, push: bool = True):
        check(program)
        if push and self._program is not None:
            self._history.append(self._program)
            del self._history[:-HISTORY_LIMIT]
            self._future.clear()
        self._program = program
        self._ops_rows = self._comp_rows = None
        self.closeSheet()
        self.historyChanged.emit()
        self._prev_shapes = []
        self._step = -1
        self.programChanged.emit()
        self._say(note)
        self.setStep(self.stepCount - 1 if keep_step else 0)
        if self._mode == "reverse":
            self._refresh_report()

    def _set_measuring(self, on: bool):
        if on != self._measuring:
            self._measuring = on
            self.measuringChanged.emit()

    def _start_measure(self):
        job = self._measure_job
        if job is None:
            return
        if self._measure_thread is not None and self._measure_thread.is_alive():
            self._measure_timer.start()           # one measurement at a time; try again when it is done
            return
        self._measure_job = None
        self._measure_thread = threading.Thread(target=self._measure, args=job, daemon=True)
        self._measure_thread.start()

    def _measure(self, program, full, comps):
        try:
            issues = [i.as_dict() for i in critique.critique(program, full, comps)]
            solids = [s for s in full if not isinstance(s.manifold, RawMesh)]
            mass = physics.properties(program, solids) if solids else None
        except Exception as e:      # a measurement bug must not leave the card on "measuring" forever
            issues, mass = [], None
            self._measured.emit(program, None, f"measurement failed: {e}")
            return
        self._measured.emit(program, issues, mass)

    def _on_measured(self, program, issues, mass):
        if program is not self._program:              # the program moved on while this was measured
            return
        if issues is None:
            self._say(str(mass))
            self._set_measuring(False)
            return
        self._issues, self._mass = issues, mass
        self._set_measuring(self._measure_job is not None)
        self.issuesChanged.emit()

    def waitMeasured(self):
        """Block until the pending measurement has landed (tests, tools); the GUI never calls this."""
        self._measure_timer.stop()
        while self._measure_job is not None or (self._measure_thread and self._measure_thread.is_alive()):
            if self._measure_job is not None and not (self._measure_thread and self._measure_thread.is_alive()):
                self._start_measure()
            if self._measure_thread:
                self._measure_thread.join()
        QCoreApplication.sendPostedEvents(self, 0)

    def _rebuild(self, prev=None):
        if not self._program:
            self._shapes, self._comps = [], []
            self.shapesChanged.emit()
            return
        t0 = time.perf_counter()
        try:
            shapes = self._ev.step(self._program, self._step)
            hits, misses = self._ev.last_hits, self._ev.last_misses
            full = self._ev.step(self._program)
        except EvalError as e:
            self._say(f"build error: {e}")
            return
        mats = self._program.get("materials", {})
        lo, hi = bounds(full)            # frame and explode on the finished build, not the partial one
        self._ground = -lo[1]
        ext = [hi[i] - lo[i] for i in range(3)]
        self._dims = [round(e, 1) for e in ext]
        self._radius = max(0.5 * (ext[0] ** 2 + ext[1] ** 2 + ext[2] ** 2) ** 0.5, 1.0)
        self._center = [(lo[0] + hi[0]) / 2, ext[1] / 2, (lo[2] + hi[2]) / 2]
        self._comps = assembly.components(self._program, full)
        if self._issues_of is not self._program:       # measured once per program version, not per scrub step
            self._issues_of = self._program
            self._measure_job = (self._program, full, self._comps)
            self._set_measuring(True)
            self._measure_timer.start()
        offsets = assembly.explode(full, self._comps)
        cinfo = {c.id: c for c in self._comps}
        cur = {s.hash for s in shapes}
        prev = prev or []
        prev_hashes = {s.hash for s in prev}
        first = not prev

        used: set[str] = set()

        def geo(s, phase):
            key = s.hash + "|" + json.dumps(mats.get(s.material), sort_keys=True)
            c = cinfo.get(s.component)
            key += "|" + s.id + "|" + (c.color if c else "") + "|" + (c.label if c else "")
            used.add(key)
            g = self._geo_cache.get(key)
            if g is None:
                g = MeshGeometry(s, mats.get(s.material), phase, c.color if c else "#8a8f98",
                                 c.label if c else s.component)
                g.materialName = s.material or ""
                self._geo_cache[key] = g
            g = g.for_step(phase)
            g.set_offset(offsets.get(s.id, [0, 0, 0]))
            return g
        out = [geo(s, 1 if (first and self._step == 0) or (not first and s.hash not in prev_hashes) else 0)
               for s in shapes]
        out += [geo(s, 2) for s in prev if s.hash not in cur]   # leaving: dematerialize on reverse playback
        self._prev_shapes = shapes
        self._shapes = out
        if len(self._geo_cache) > GEO_CACHE_LIMIT:      # scrubbing a parameter leaves a trail of old meshes
            self._geo_cache = {k: g for k, g in self._geo_cache.items() if k in used}
            self._ev.trim(EVAL_CACHE_LIMIT)
        self._ops_rows = self._comp_rows = None
        live = [g for g, s in zip(out, shapes)]
        self._stats = {"triangles": sum(g.triangles for g in live), "parts": len(live),
                       "components": len(self._comps), "buildMs": round((time.perf_counter() - t0) * 1000, 1),
                       "cacheHits": hits, "cacheMisses": misses, "cached": len(self._ev._cache)}
        self.shapesChanged.emit()

    def _load_explanation(self):
        """A new object: forget the old explanation, pick up a saved one from the project folder."""
        self.stopSpeaking()
        doc = {}
        f = (self._project / "explanation.json") if self._project else None
        if f and f.exists():
            try:
                doc = json.loads(f.read_text())
            except ValueError:
                doc = {}
        self._explanation = doc
        self.explanationChanged.emit()

    def _refresh_report(self):
        if not self._program:
            return
        rep = (self._project / "reverse_report.json") if self._project else None
        if rep and rep.exists() and (self._program.get("name", "").startswith("Reverse:") or self._program.get("reference")):
            try:
                self._report = json.loads(rep.read_text())
            except (OSError, json.JSONDecodeError) as e:
                self._say(f"reverse report unreadable ({e}); showing the program's own report")
                self._report = reverse.program_report(self._program, self._ev.step(self._program))
        else:
            self._report = reverse.program_report(self._program, self._ev.step(self._program))
        self.reportChanged.emit()

    # ------------------------------------------------------------------ timeline
    @Slot(int)
    def setStep(self, k: int):
        if not self._program:
            return
        k = max(0, min(int(k), self.stepCount - 1))
        if k == self._step:
            return
        prev = self._prev_shapes if self._step >= 0 else []
        self._step = k
        self.stepChanged.emit()
        self._rebuild(prev)

    # ------------------------------------------------------------------ modes and selection
    @Slot(str)
    def setMode(self, m: str):
        if m not in MODES or m == self._mode:
            return
        if self._mode == "present":
            self.stopSpeaking()
        self._mode = m
        if m == "present" and self._program:
            self._rest = explain.rest_pose(self._ev.step(self._program))
        self.modeChanged.emit()
        if m == "reverse":
            self._refresh_report()

    @Slot(str)
    def select(self, oid: str):
        self._selected = oid
        self.selectionChanged.emit()

    @Slot(str)
    def setEngine(self, name: str):
        self._engine = name

    # ------------------------------------------------------------------ files
    @Slot(str)
    def openFile(self, path: str):
        p = _local(path)
        if p.suffix.lower() in importers.ROUTES:
            return self.importModel(str(p))
        try:
            prog = json.loads(p.read_text())
            self._epoch += 1
            self._project = p.parent
            self._ev = Evaluator(self._project)
            self._history.clear()
            self._future.clear()
            self._geo_cache.clear()
            self._program = None
            self._report = {}
            self._set_program(prog, f"opened {p.name}")
            self._load_explanation()
        except (OSError, json.JSONDecodeError, ProgramError, EvalError) as e:
            self._say(f"open failed: {e}")

    @Slot(str)
    def importModel(self, path: str):
        """Reverse engineering: any supported 3D file (mesh, CAD, Blender scene, gallery ZIP) into pieces and
        components, with an evidence ledger."""
        src = _local(path)
        try:
            kind = importers.route(src)
        except ValueError as e:
            return self._say(f"import refused: {e}")
        proj = OUT / "reverse" / (src.stem + time.strftime("-%Y%m%d-%H%M%S"))

        def job(log):
            log(f"import: {src.name} ({kind.label})")
            proj.mkdir(parents=True, exist_ok=True)
            glb, what = importers.prepare(src, proj / "import", log=log)
            prog, rep = reverse.analyze_mesh(glb, proj)
            rep["input"].update(file=src.name, format=what)
            (proj / "reverse_report.json").write_text(json.dumps(rep, indent=1))
            log(f"reverse: {len(prog['ops'])} pieces, {len(prog['components'])} components, "
                f"{len(rep['ledger'])} ledger entries")
            return {"program": prog, "project": str(proj)}
        self._run_job("Reverse engineering", job, mode_after="reverse")

    @Slot(str, bool)
    def imageTo3D(self, path: str, single: bool):
        """Image or Holodeck sheet -> a 3D model via Hunyuan3D in ComfyUI (one Berth batch)."""
        src = _local(path)

        def job(log):
            log(f"image3d: {src.name}")
            info = pipeline.image_to_mesh(src, single=single, log=log)
            prog = json.loads(Path(info["program"]).read_text())
            log(f"image3d: ready, {info['parts']} part(s), {info['triangles']:,} triangles "
                f"({info['gpu_seconds']} s on the card)")
            return {"program": prog, "project": str(Path(info["program"]).parent)}
        self._run_job("Image to 3D", job, mode_after="reverse")

    # ------------------------------------------------------------------ edits
    def _commit_op(self, oid: str, mutate, note: str) -> bool:
        try:
            prog = copy.deepcopy(self._program)
            op = next(o for o in prog["ops"] if o["id"] == oid)
            mutate(op)
            self._ev.step(prog)              # validates on the shared cache: only the edited op is rebuilt
            keep = self._step
            self._set_program(prog, note, keep_step=True)
            if keep < self.stepCount - 1:
                self.setStep(keep)
            self.select(op["id"])
            return True
        except (StopIteration, json.JSONDecodeError, ProgramError, EvalError, TypeError, ValueError) as e:
            self._say(f"edit rejected: {e}")
            self.selectionChanged.emit()
            return False

    @Slot(str, str, str, result=bool)
    def setParam(self, oid: str, key: str, value_json: str) -> bool:
        try:
            value = json.loads(value_json)
        except json.JSONDecodeError as e:
            self._say(f"edit rejected: {e}")
            return False

        def mutate(op):
            if key in ("label", "material"):
                if value in ("", None):
                    op.pop(key, None)
                else:
                    op[key] = value
            else:
                op.setdefault("params", {})[key] = value
        return self._commit_op(oid, mutate, f"{oid}.{key} = {value_json[:60]}")

    @Slot(str, float, float, float, result=bool)
    def nudge(self, oid: str, dx: float, dy: float, dz: float) -> bool:
        """Gizmo move: add to the op's translate (applied last, so it moves the finished part)."""
        def mutate(op):
            t = op.setdefault("params", {}).get("translate", [0, 0, 0])
            op["params"]["translate"] = [round(t[0] + dx, 3), round(t[1] + dy, 3), round(t[2] + dz, 3)]
        return self._commit_op(oid, mutate, f"moved {oid} by ({dx:.1f}, {dy:.1f}, {dz:.1f})")

    @Slot(str, result=bool)
    def applyOpJson(self, text: str) -> bool:
        try:
            new_op = json.loads(text)
        except json.JSONDecodeError as e:
            self._say(f"edit rejected: {e}")
            return False
        return self._commit_op(self._selected, lambda op: (op.clear(), op.update(new_op)),
                               f"edited {new_op.get('id')}")

    @Slot(str)
    def addPrimitive(self, kind: str):
        """Tool palette: append a primitive at the origin (or start a new program with it)."""
        defaults = {"box": {"size": [100, 100, 100]}, "cylinder": {"height": 120, "radius": 40},
                    "sphere": {"radius": 60}, "torus": {"major_radius": 60, "minor_radius": 15},
                    "capsule": {"height": 100, "radius": 30}, "gear": {"teeth": 24, "module": 4, "thickness": 20,
                                                                        "bore": 12},
                    "helix": {"radius": 30, "pitch": 12, "turns": 6, "wire_radius": 3},
                    "loft": {"sections": [{"y": 0, "rx": 60, "rz": 35}, {"y": 80, "radius": 40},
                                          {"y": 160, "rx": 20, "rz": 45}]},
                    "pipe": {"path": [[-80, 20, 0], [0, 120, 0], [80, 20, 0]], "radius": 10, "smooth": 8},
                    "tube": {"height": 160, "radius": 60, "wall": 4},
                    "nozzle": {"throat_radius": 20, "expansion_ratio": 16, "contraction_ratio": 4},
                    "rotor": {"hub_radius": 22, "tip_radius": 90, "chord": 32, "blades": 16},
                    "grille": {"size": [140, 3, 140], "hole_size": 8, "hole": "hex"}}
        if kind not in defaults:
            return
        prog = copy.deepcopy(self._program) if self._program else {
            "version": 1, "name": "Untitled build", "units": "mm", "materials": {
                "steel": {"base_color": [0.62, 0.64, 0.68], "metalness": 1.0, "roughness": 0.3}}, "ops": []}
        prog.setdefault("materials", {}).setdefault(
            "steel", {"base_color": [0.62, 0.64, 0.68], "metalness": 1.0, "roughness": 0.3})
        ids = {o["id"] for o in prog["ops"]}
        n = 1
        while f"{kind}_{n}" in ids:
            n += 1
        oid = f"{kind}_{n}"
        prog["ops"].append({"id": oid, "op": kind, "label": f"{kind.title()} {n}", "component": oid,
                            "material": "steel", "params": defaults[kind]})
        if "components" in prog:
            prog["components"].append({"id": oid, "label": f"{kind.title()} {n}"})
        self._set_program(prog, f"added {oid}", keep_step=True)
        self.select(oid)

    @Slot()
    def undo(self):
        if not self._history:
            self._say("nothing to undo")
            return
        self._future.append(self._program)
        self._set_program(self._history.pop(), "undo", keep_step=True, push=False)

    @Slot()
    def redo(self):
        if not self._future:
            self._say("nothing to redo")
            return
        self._history.append(self._program)
        self._set_program(self._future.pop(), "redo", keep_step=True, push=False)

    @Slot(str, result=bool)
    def applyMaterial(self, name: str) -> bool:
        """Material shelf: paint the selected part, or every part of the selected component."""
        if not self._program:
            return False
        ids = [g.shapeId for g in self._shapes
               if g.shapeId == self._selected or g.component == self._selected]
        if not ids and self._op(self._selected):
            ids = [self._selected]
        try:
            prog = materials.apply(copy.deepcopy(self._program), ids, name)
            keep, sel = self._step, self._selected
            self._set_program(prog, f"material {name} on {len(ids)} part(s)", keep_step=True)
            if keep < self.stepCount - 1:
                self.setStep(keep)
            self.select(sel)
            return True
        except (ValueError, ProgramError, EvalError) as e:
            self._say(f"material rejected: {e}")
            return False

    @Slot(str, str, result=bool)
    def swapMaterial(self, old: str, preset: str) -> bool:
        """Whole-build material variant: every part made of `old` becomes `preset`, as one undo step."""
        if not self._program:
            return False
        try:
            prog = materials.swap(copy.deepcopy(self._program), old, preset)
            keep, sel = self._step, self._selected
            self._set_program(prog, f"material variant: {old} -> {preset}", keep_step=True)
            if keep < self.stepCount - 1:
                self.setStep(keep)
            self.select(sel)
            return True
        except (ValueError, ProgramError, EvalError) as e:
            self._say(f"material swap rejected: {e}")
            return False

    @Slot(float)
    def rescale(self, factor: float):
        """Scale the whole build about the origin, e.g. an import whose units were metres, as one undo step."""
        if not self._program:
            return
        try:
            prog = scale_program(self._program, factor)
            self._ev.step(prog)
        except (ProgramError, EvalError) as e:
            return self._say(f"rescale refused: {e}")
        self._set_program(prog, f"scaled the build by {factor:g}", keep_step=True)

    @Slot()
    def closeProgram(self):
        """Back to the start screen."""
        self._epoch += 1
        self._program = None
        self._project = None
        self._history.clear()
        self._future.clear()
        self._geo_cache.clear()
        self._ev = Evaluator()
        self._ops_rows = self._comp_rows = None
        self._prev_shapes = []
        self._step = -1
        self._selected = ""
        self._report = {}
        self._stats = {}
        self._dims = []
        self._explanation = {}
        self._issues, self._issues_of, self._mass, self._measure_job = [], None, None, None
        self._measure_timer.stop()
        self._set_measuring(False)
        self.issuesChanged.emit()
        self.explanationChanged.emit()
        self.stopSpeaking()
        self.programChanged.emit()
        self.historyChanged.emit()
        self.selectionChanged.emit()
        self.stepChanged.emit()
        self.reportChanged.emit()
        self.libraryChanged.emit()
        self._rebuild()

    # ------------------------------------------------------------------ model jobs
    @Slot(str)
    def dream(self, text: str):
        engine, cfg = self._engine, dict(self._cfg)

        def job(log):
            sources = None
            if cfg["research"]:      # ground the concept in real mechanisms before the blueprint is written
                from ..research import lane
                qs = client.research_queries(text, [], engine, log=log)
                sources = lane.gather(qs, [text], cfg["search_url"], log=log) or None
            return {"program": client.dream(text, engine, log=log, sources=sources)}
        self._run_job("Specifying", job)

    @Slot(str)
    def edit(self, text: str):
        if not self._program:
            return self.dream(text)
        self._agent_edit("Editing", text)

    def _agent_edit(self, label: str, text: str, scope: set[str] | None = None):
        base, engine, current = copy.deepcopy(self._program), self._engine, self._program

        def job(log):
            patch = client.edit(base, text, engine, log=log, scope=scope)
            log(f"patch: {len(patch)} change(s)")
            return {"program": apply_patch(base, patch), "keep": True, "base": current}
        self._run_job(label, job)

    @Slot()
    def fixIssues(self):
        """Hand the critic's measured problems to the model as one scoped edit."""
        if self._measuring:
            return self._say("still measuring this version; try again in a moment")
        if not self._program or not self._issues:
            return self._say("no accuracy issues to fix")
        issues = [critique.Issue(**i) for i in self._issues]
        scope = {o for i in issues if i.subject for o in component_ops(self._program, i.subject)}
        self._agent_edit("Fixing", client.fix_instruction(issues), scope or None)

    @Slot(str, str)
    def rework(self, cid: str, text: str):
        """Agent edit limited to one component: every op outside it must come back unchanged."""
        if not self._program or not text.strip():
            return
        scope = set(component_ops(self._program, cid))
        if not scope:
            return self._say(f"rework: no component {cid}")
        label = next((c.label for c in self._comps if c.id == cid), cid)
        self._agent_edit(f"Reworking {label}", f"Rework the part {label!r}: {text.strip()}", scope)

    @Slot(str)
    def deleteComponent(self, cid: str):
        try:
            prog = delete_component(self._program, cid)
            self._ev.step(prog)
        except (ProgramError, EvalError, TypeError) as e:
            return self._say(f"delete refused: {e}")
        self._selected = ""
        self._set_program(prog, f"deleted {cid}", keep_step=True)
        self.selectionChanged.emit()

    @Slot(str)
    def duplicateComponent(self, cid: str):
        c = next((c for c in self._comps if c.id == cid), None)
        if c is None:
            return self._say(f"duplicate: no component {cid}")
        try:
            prog, new = duplicate_component(self._program, cid, [round(float(c.hi[0] - c.lo[0]) * 1.15, 1), 0, 0])
            self._ev.step(prog)
        except (ProgramError, EvalError, TypeError) as e:
            return self._say(f"duplicate refused: {e}")
        self._set_program(prog, f"duplicated {cid} as {new}", keep_step=True)
        self.select(new)

    @Slot()
    def nameParts(self):
        """Inferred names for components from their observed measurements (local model, tagged inferred)."""
        if not self._program:
            return
        prog, current = copy.deepcopy(self._program), self._program
        facts = [{"id": c.id, "current_label": c.label, "pieces": len(c.shapes),
                  "extent": (c.hi - c.lo).round(1).tolist(), "center": c.center.round(1).tolist()}
                 for c in self._comps]
        context = self.title

        def job(log):
            names = client.name_components(facts, context, self._engine, log=log)
            comps = prog.setdefault("components", [{"id": f["id"], "label": f["current_label"]} for f in facts])
            for c in comps:
                if c["id"] in names:
                    c["label"] = names[c["id"]].get("label", c.get("label", c["id"]))
                    c["role"] = names[c["id"]].get("role", "")
            return {"program": prog, "keep": True, "names": names, "base": current}
        self._run_job("Naming parts", job)

    def _run_job(self, label: str, fn, mode_after: str | None = None):
        if self._busy:
            self._say("busy: one job at a time (one GPU)")
            return
        local = label.startswith(("Reverse", "Render", "Opening", "Pulling", "Image to 3D", "Drawing"))
        self.stopSpeaking()
        self._busy = label if local else f"{label} on {self._engine}"
        self.busyChanged.emit()
        self._mode_after = mode_after

        epoch = self._epoch

        def run():
            try:
                res = fn(lambda m: self._jobDone.emit(None, "log:" + m))
                if isinstance(res, dict):
                    res["epoch"] = epoch
                self._jobDone.emit(res, "done")
            except Exception as e:  # noqa: BLE001 - every failure is reported in the console
                self._jobDone.emit(None, f"failed: {e}")
        threading.Thread(target=run, daemon=True).start()

    def _on_job(self, res, msg: str):
        if msg.startswith("log:"):
            self._say(msg[4:])
            return
        self._busy = ""
        self.busyChanged.emit()
        if res is None:
            self._say(msg)
            return
        if res.get("epoch", self._epoch) != self._epoch:
            if "program" in res and "project" not in res and "base" not in res:
                OUT.mkdir(parents=True, exist_ok=True)
                saved = OUT / time.strftime("%Y%m%d-%H%M%S.json")
                saved.write_text(json.dumps(res["program"], indent=1))
                self.libraryChanged.emit()
                return self._say(f"finished after you switched builds; saved to {saved} (open it from Recents)")
            return self._say("a job finished for a build that is no longer open; its result was dropped")
        if "note" in res:
            self._say(res["note"])
            return
        if "explanation" in res:
            self._explanation = res["explanation"]
            self.explanationChanged.emit()
            c = self._explanation["counts"]
            self._say(f"explained: {len(self._explanation['chapters'])} chapters, {c['cited']} cited, "
                      f"{c['measured']} measured, {c['concept']} concept, {self._explanation['dropped']} dropped")
            self.setMode("present")
            return
        if "sheet" in res:
            self._sheet = res["sheet"]
            self.sheetChanged.emit()
            return self._say(f"blueprint sheet ready ({self._sheet['seconds']} s): {self._sheet['svg']}")
        if "render" in res:
            self._render_path = res["render"]
            self.renderChanged.emit()
            self._say(f"render ready ({res.get('seconds', 0):.0f} s): {res['render']}")
            return
        prog = res.get("program")
        if prog is None:
            return
        if "base" in res and res["base"] is not self._program:
            self._say("agent result dropped: the build changed while the model was working (nothing lost; ask again)")
            return
        if "project" in res:
            self._project = Path(res["project"])
            self._ev = Evaluator(self._project)
            self._history.clear()
            self._future.clear()
            self._geo_cache.clear()
            self._program = None
        elif "names" not in res:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / time.strftime("%Y%m%d-%H%M%S.json")).write_text(json.dumps(prog, indent=1))
            self.libraryChanged.emit()
        self._set_program(prog, f"built: {prog.get('name', '')} ({len(prog['ops'])} steps)",
                          keep_step=res.get("keep", False) or bool(self._mode_after))
        if "keep" not in res:
            self._load_explanation()
        if self._mode_after:
            self.setMode(self._mode_after)
            self._mode_after = None
        if "names" in res:
            self._report.setdefault("ledger", []).extend(
                reverse.ledger_entry(f"{v.get('label')}: {v.get('role', '')}", "inferred",
                                     f"local model {self._engine}, from observed size and position", subject=k,
                                     confidence=v.get("confidence", 0.5)) for k, v in res["names"].items())
            for item in self._report.get("checklist", []):
                if item["q"].startswith("What is each part called"):
                    item.update(status="partly answered", by=f"inferred by {self._engine}")
            if self._project and (self._project / "reverse_report.json").exists():
                (self._project / "reverse_report.json").write_text(json.dumps(self._report, indent=1))
            self.reportChanged.emit()

    # ------------------------------------------------------------------ export and render
    @Slot(str, result=str)
    def exportAs(self, fmt: str) -> str:
        if not self._program or fmt not in ("glb", "stl", "obj", "3mf"):
            return ""
        name = "".join(c if c.isalnum() else "-" for c in self.title.lower()).strip("-") or "build"
        path, n = OUT / f"{name}.{fmt}", 2
        while path.exists():                    # never overwrite an earlier export
            path, n = OUT / f"{name}-{n}.{fmt}", n + 1
        try:
            OUT.mkdir(parents=True, exist_ok=True)
            shapes = self._ev.step(self._program)
            if fmt == "stl" and any(isinstance(s.manifold, RawMesh) for s in shapes):
                raise ValueError("imported pieces that are not watertight cannot go to STL")
            exporter.export(shapes, self._program.get("materials", {}), path)
            self._say(f"exported {path}")
            return str(path)
        except (OSError, ValueError, EvalError, ImportError) as e:
            path.unlink(missing_ok=True)
            self._say(f"export failed: {e}" + (" (3MF needs core support that is not installed)" if fmt == "3mf" else ""))
            return ""

    @Slot(str)
    def renderShowcase(self, camera_json: str):
        """Path-traced still from the current camera: Blender Cycles on the CPU (no GPU), OIDN denoised."""
        if not self._program:
            return
        from ..core import render
        try:
            cam = json.loads(camera_json)
            work = OUT / "renders"
            work.mkdir(parents=True, exist_ok=True)
            stamp = time.strftime("%Y%m%d-%H%M%S")
            shapes = self._ev.step(self._program)
            glb = exporter.export(shapes, self._program.get("materials", {}), work / f"{stamp}.glb")
        except (OSError, ValueError, EvalError) as e:
            return self._say(f"render failed: {e}")
        mats = self._program.get("materials", {})
        part_mats = {s.id: s.material for s in shapes if s.material}
        ground = self._ground

        def job(log):
            log("render: Blender Cycles on the CPU (32 threads), about a minute")
            t = time.time()
            png = render.cycles_still(glb, work / f"{stamp}.png", cam, mats, ground=ground, log=log,
                                      part_materials=part_mats)
            return {"render": str(png), "seconds": time.time() - t}
        self._run_job("Rendering (Cycles, CPU)", job)

    @Slot()
    def openInBlender(self):
        """Hand the build to Blender (mcp-for-blender socket on localhost:9876) for agents or hand edits."""
        if not self._program:
            return
        from ..core import blender_link
        try:
            work = OUT / "blender"
            work.mkdir(parents=True, exist_ok=True)
            shapes = self._ev.step(self._program)
            glb = exporter.export(shapes, self._program.get("materials", {}),
                                  work / time.strftime("%Y%m%d-%H%M%S.glb"))
        except (OSError, ValueError, EvalError) as e:
            return self._say(f"Blender hand-off failed: {e}")
        mats = self._program.get("materials", {})
        labels = {c.id: c.label for c in assembly.components(self._program, shapes)}
        parts = {s.id: {"id": s.id, "label": s.label, "component": s.component,
                        "component_label": labels.get(s.component, s.component), "material": s.material}
                 for s in shapes}

        def job(log):
            if blender_link.is_up():
                raise RuntimeError("a Blender with the MCP socket is already open (localhost:9876); close it first")
            blender_link.open_in_blender(glb, mats, parts)
            log("blender: starting (iGPU, CUDA hidden, update check off)")
            if not blender_link.wait_up(60):
                raise RuntimeError("Blender opened but the MCP socket did not come up on localhost:9876")
            info = blender_link.send("get_scene_info")
            log(f"blender: MCP socket up on localhost:9876 ({info.get('status')})")
            return {"note": "Blender is live: agents can drive it through mcp-for-blender; Pull brings it back."}
        self._run_job("Opening Blender", job)

    @Slot()
    def pullFromBlender(self):
        """Bring the live Blender scene back as a reverse-engineered program (Dissect, Timeline, Showcase)."""
        from ..core import blender_link
        dest = OUT / "blender" / time.strftime("pulled-%Y%m%d-%H%M%S.glb")
        dest.parent.mkdir(parents=True, exist_ok=True)
        proj = OUT / "reverse" / dest.stem

        def job(log):
            if not blender_link.is_up():
                raise RuntimeError("no Blender MCP socket on localhost:9876 (use Open in Blender first)")
            blender_link.pull_scene(dest)
            log(f"blender: exported {dest.name}; reverse engineering it")
            proj.mkdir(parents=True, exist_ok=True)
            prog, rep = reverse.analyze_mesh(dest, proj)
            prog["name"] = "Reverse: from Blender"
            return {"program": prog, "project": str(proj)}
        self._run_job("Pulling from Blender", job, mode_after="reverse")

    @Slot()
    def clearRender(self):
        if self._render_path:
            self._render_path = ""
            self.renderChanged.emit()

    # ------------------------------------------------------------------ explain
    @Slot()
    def explain(self):
        """How the open object works: research lane -> local model -> every sentence checked (core/explain.py)."""
        if not self._program:
            return
        prog, comps, dims = self._program, list(self._comps), list(self._dims)
        subject = self.title.removeprefix("Reverse: ")
        bp = prog.get("blueprint") or {}
        dreamed = bool(bp.get("parts"))
        origin = ("a concept dreamed by a local model from a text prompt" if dreamed else
                  "a 3D shape generated from a picture" if prog.get("reference") else
                  "an imported 3D model that was taken apart into pieces" if subject != self.title else
                  "a model built by hand in the workshop")
        facts = explain.component_facts(comps, dims, prog.get("units", "mm"))
        glance = explain.at_a_glance(subject, comps, dims, prog.get("units", "mm"))
        rest = explain.rest_pose(self._ev.step(prog))
        engine, cfg, project = self._engine, dict(self._cfg), self._project
        labels = [c.label for c in comps if not c.label.lower().startswith(("detached", "piece", "body"))]

        def job(log):
            from ..research import lane
            sources = [dict(s) for s in bp.get("sources", [])]
            if cfg["research"]:
                qs = client.research_queries(subject + (". " + bp.get("summary", "") if bp.get("summary") else ""),
                                             labels, engine, log=log)
                found = lane.gather(qs, [subject] + labels, cfg["search_url"], log=log)
                sources = [s.as_dict() for s in found] or sources
            else:
                log("explain: web research is off (Preferences); only measurements"
                    + (" and concept reasoning" if dreamed else "") + " can be shown")
            block = lane.context_block([lane.Source(**s) for s in sources])
            raw = client.explain(subject, origin, facts, block, engine, log=log)
            checked = explain.verify(raw, sources, facts, force_concept=dreamed)
            doc = explain.finish(subject, checked, glance, sources, rest, engine)
            doc["research"] = bool(cfg["research"])
            if project:
                (project / "explanation.json").write_text(json.dumps(doc, indent=1))
            return {"explanation": doc}
        self._run_job("Explaining", job)

    @Slot(str, str)
    def setService(self, key: str, value_json: str):
        if key not in config.DEFAULTS:
            return
        try:
            v = json.loads(value_json)
        except ValueError:
            return
        if not isinstance(v, type(config.DEFAULTS[key])):
            return
        self._cfg[key] = v.strip() if isinstance(v, str) else v
        config.save(self._cfg)
        self.servicesChanged.emit()

    # ------------------------------------------------------------------ voice (optional; never on the RTX card)
    @Slot(str)
    def speak(self, text: str):
        """Read `text` aloud. Emits voiceChanged when it starts and when it ends."""
        self.stopSpeaking()
        if not text.strip():
            return
        self._say_token += 1
        token, cfg = self._say_token, dict(self._cfg)
        self._speaking = True
        self.voiceChanged.emit()

        def run():
            try:
                wav = voice.synthesize(text, cfg)
                if token != self._say_token:
                    return
                self._player = voice.player(wav)
                self._player.wait()
                wav.unlink(missing_ok=True)
                self._voiceEvent.emit("said", str(token))
            except Exception as e:  # noqa: BLE001 - reported in the console, the presentation carries on silently
                self._voiceEvent.emit("error", f"{token}|voice: {e}")
        threading.Thread(target=run, daemon=True).start()

    @Slot()
    def stopSpeaking(self):
        self._say_token += 1
        if self._player and self._player.poll() is None:
            self._player.terminate()
        self._player = None
        if self._speaking:
            self._speaking = False
            self.voiceChanged.emit()

    @Slot()
    def toggleDictation(self):
        """First call starts recording the microphone, the second stops it and transcribes (signal `dictated`)."""
        if self._rec is None:
            try:
                self._rec = voice.recorder()
            except RuntimeError as e:
                self._say(f"dictation: {e}")
                return
            self._listening = True
            self.voiceChanged.emit()
            return
        proc, wav = self._rec
        self._rec = None
        proc.terminate()
        self._listening = False
        self.voiceChanged.emit()
        cfg = dict(self._cfg)

        def run():
            try:
                proc.wait(timeout=5)
                self._voiceEvent.emit("heard", voice.transcribe(wav, cfg))
            except Exception as e:  # noqa: BLE001
                self._voiceEvent.emit("error", f"0|dictation: {e}")
            finally:
                wav.unlink(missing_ok=True)
        threading.Thread(target=run, daemon=True).start()

    def _on_voice(self, kind: str, payload: str):
        if kind == "heard":
            self._say(f"dictation: “{payload}”")
            self.dictated.emit(payload)
        elif kind == "said":
            if payload == str(self._say_token) and self._speaking:
                self._speaking = False
                self.voiceChanged.emit()
        else:
            token, _, msg = payload.partition("|")
            self._say(msg)
            if token in ("0", str(self._say_token)) and self._speaking:
                self._speaking = False
                self.voiceChanged.emit()
