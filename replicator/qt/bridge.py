"""Studio: the one QObject QML talks to. Owns the program, evaluator, timeline cursor, modes, components, the
reverse-engineering ledger, and the model / render jobs."""
from __future__ import annotations

import copy
import json
import threading
import time
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot

from ..core import assembly, reverse
from ..core import export as exporter
from ..core.evaluate import EvalError, Evaluator, RawMesh, bounds, component_map
from ..core.program import ProgramError, apply_patch, check, op_inputs
from ..llm import client
from .envmap import EnvMap
from .mesh_geometry import MeshGeometry

OUT = Path.home() / "Replicator"
MODES = ("build", "dissect", "reverse", "showcase")
ENUMS = {"mode": {"boolean": ["union", "difference", "intersection"], "array": ["linear", "radial", "mirror"],
                  "deform": ["taper", "twist", "bend"]},
         "axis": ["x", "y", "z"]}


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
    _jobDone = Signal(object, str)

    def __init__(self):
        super().__init__()
        self._ev = Evaluator()
        self._program: dict | None = None
        self._project: Path | None = None
        self._history: list[dict] = []
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
        self._ground = 0.0
        self._radius = 300.0
        self._center = [0.0, 150.0, 0.0]
        self._env = EnvMap()
        self._jobDone.connect(self._on_job)

    # ------------------------------------------------------------------ properties
    @Property("QVariantList", notify=shapesChanged)
    def shapes(self):
        return self._shapes

    @Property("QVariantList", notify=shapesChanged)
    def ops(self):
        if not self._program:
            return []
        comp = component_map(self._program)
        colors = {c.id: c.color for c in self._comps}
        consumed_at: dict[str, int] = {}
        for i, op in enumerate(self._program["ops"]):
            for ref in op_inputs(op):
                consumed_at.setdefault(ref, i)
        return [{"id": op["id"], "op": op["op"], "label": op.get("label", op["id"]), "part": op.get("part", ""),
                 "component": comp[op["id"]], "color": colors.get(comp[op["id"]], "#8a8f98"), "index": i,
                 "consumedAt": consumed_at.get(op["id"], -1)}
                for i, op in enumerate(self._program["ops"])]

    @Property("QVariantList", notify=shapesChanged)
    def components(self):
        g = self._ground
        return [{"id": c.id, "label": c.label, "role": c.role, "color": c.color, "count": len(c.shapes),
                 "order": c.order, "shapes": c.shapes,
                 "center": [float(c.center[0]), float(c.center[1]) + g, float(c.center[2])],
                 "offset": [float(x) for x in (c.offset if c.offset is not None else [0, 0, 0])],
                 "size": [float(x) for x in (c.hi - c.lo)]} for c in self._comps]

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
        return self._log[-1] if self._log else "Ready. Dream something, or import a model to take apart."

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
                rows.append({"key": k, "kind": "number", "value": float(v)})
            elif k in ENUMS and isinstance(v, str):
                opts = ENUMS[k] if isinstance(ENUMS[k], list) else ENUMS[k].get(op["op"], [v])
                rows.append({"key": k, "kind": "enum", "value": v, "options": opts})
            elif isinstance(v, list) and len(v) == 3 and all(isinstance(x, (int, float)) for x in v):
                rows.append({"key": k, "kind": "vec3", "value": [float(x) for x in v]})
            else:
                rows.append({"key": k, "kind": "json", "value": json.dumps(v)})
        for k in ("translate", "rotate", "scale"):
            v = params.get(k)
            if isinstance(v, (int, float)):
                v = [float(v)] * 3
            rows.append({"key": k, "kind": "vec3", "group": "Coordinates",
                         "value": [float(x) for x in v] if v else ([1.0] * 3 if k == "scale" else [0.0] * 3)})
        return rows

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

    @Property(str, notify=renderChanged)
    def renderPath(self):
        return self._render_path

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
        self._program = program
        self._prev_shapes = []
        self._step = -1
        self.programChanged.emit()
        self._say(note)
        self.setStep(self.stepCount - 1 if keep_step else 0)
        if self._mode == "reverse":
            self._refresh_report()

    def _rebuild(self, prev=None):
        if not self._program:
            self._shapes, self._comps = [], []
            self.shapesChanged.emit()
            return
        try:
            shapes = self._ev.step(self._program, self._step)
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
        offsets = assembly.explode(full, self._comps)
        cinfo = {c.id: c for c in self._comps}
        cur = {s.hash for s in shapes}
        prev = prev or []
        prev_hashes = {s.hash for s in prev}
        first = not prev

        def geo(s, phase):
            key = s.hash + "|" + json.dumps(mats.get(s.material), sort_keys=True)
            g = self._geo_cache.get(key)
            c = cinfo.get(s.component)
            if g is None:
                g = MeshGeometry(s, mats.get(s.material), phase, c.color if c else "#8a8f98",
                                 c.label if c else s.component)
                self._geo_cache[key] = g
            g.with_phase(phase)
            g.set_offset(offsets.get(s.id, [0, 0, 0]))
            return g
        out = [geo(s, 1 if (first and self._step == 0) or (not first and s.hash not in prev_hashes) else 0)
               for s in shapes]
        out += [geo(s, 2) for s in prev if s.hash not in cur]   # leaving: dematerialize on reverse playback
        self._prev_shapes = shapes
        self._shapes = out
        self.shapesChanged.emit()

    def _refresh_report(self):
        if not self._program:
            return
        rep = (self._project / "reverse_report.json") if self._project else None
        if rep and rep.exists() and (self._program.get("name", "").startswith("Reverse:") or self._program.get("reference")):
            self._report = json.loads(rep.read_text())
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
        self._mode = m
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
        if p.suffix.lower() in (".glb", ".gltf", ".obj", ".stl", ".ply", ".off"):
            return self.importModel(str(p))
        try:
            prog = json.loads(p.read_text())
            self._project = p.parent
            self._ev = Evaluator(self._project)
            self._history.clear()
            self._program = None
            self._report = {}
            self._set_program(prog, f"opened {p.name}")
        except (OSError, json.JSONDecodeError, ProgramError, EvalError) as e:
            self._say(f"open failed: {e}")

    @Slot(str)
    def importModel(self, path: str):
        """Reverse engineering: decompose a GLB/OBJ/STL into pieces and components, with an evidence ledger."""
        src = _local(path)
        proj = OUT / "reverse" / (src.stem + time.strftime("-%Y%m%d-%H%M%S"))

        def job(log):
            log(f"reverse: reading {src.name}")
            proj.mkdir(parents=True, exist_ok=True)
            prog, rep = reverse.analyze_mesh(src, proj)
            log(f"reverse: {len(prog['ops'])} pieces, {len(prog['components'])} components, "
                f"{len(rep['ledger'])} ledger entries")
            return {"program": prog, "project": str(proj)}
        self._run_job("Reverse engineering", job, mode_after="reverse")

    # ------------------------------------------------------------------ edits
    def _commit_op(self, oid: str, mutate, note: str) -> bool:
        try:
            prog = copy.deepcopy(self._program)
            op = next(o for o in prog["ops"] if o["id"] == oid)
            mutate(op)
            Evaluator(self._project).step(prog)
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
                    "pipe": {"path": [[-80, 20, 0], [0, 120, 0], [80, 20, 0]], "radius": 10, "smooth": 8}}
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
        self._set_program(prog, f"added {oid}", keep_step=True)
        self.select(oid)

    @Slot()
    def undo(self):
        if not self._history:
            self._say("nothing to undo")
            return
        self._set_program(self._history.pop(), "undo", keep_step=True, push=False)

    # ------------------------------------------------------------------ model jobs
    @Slot(str)
    def dream(self, text: str):
        self._run_job("Dreaming", lambda log: {"program": client.dream(text, self._engine, log=log)})

    @Slot(str)
    def edit(self, text: str):
        if not self._program:
            return self.dream(text)
        base = copy.deepcopy(self._program)

        def job(log):
            patch = client.edit(base, text, self._engine, log=log)
            log(f"patch: {len(patch)} change(s)")
            return {"program": apply_patch(base, patch), "keep": True}
        self._run_job("Editing", job)

    @Slot()
    def nameParts(self):
        """Inferred names for components from their observed measurements (local model, tagged inferred)."""
        if not self._program:
            return
        prog = copy.deepcopy(self._program)
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
            return {"program": prog, "keep": True, "names": names}
        self._run_job("Naming parts", job)

    def _run_job(self, label: str, fn, mode_after: str | None = None):
        if self._busy:
            self._say("busy: one job at a time (one GPU)")
            return
        local = label.startswith(("Reverse", "Render", "Opening", "Pulling"))
        self._busy = label if local else f"{label} on {self._engine}"
        self.busyChanged.emit()
        self._mode_after = mode_after

        def run():
            try:
                self._jobDone.emit(fn(lambda m: self._jobDone.emit(None, "log:" + m)), "done")
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
        if "note" in res:
            self._say(res["note"])
            return
        if "render" in res:
            self._render_path = res["render"]
            self.renderChanged.emit()
            self._say(f"render ready ({res.get('seconds', 0):.0f} s): {res['render']}")
            return
        prog = res["program"]
        if "project" in res:
            self._project = Path(res["project"])
            self._ev = Evaluator(self._project)
            self._history.clear()
            self._program = None
        elif "names" not in res:
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / time.strftime("%Y%m%d-%H%M%S.json")).write_text(json.dumps(prog, indent=1))
        self._set_program(prog, f"built: {prog.get('name', '')} ({len(prog['ops'])} steps)",
                          keep_step=res.get("keep", False) or bool(self._mode_after))
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
        if not self._program:
            return ""
        OUT.mkdir(parents=True, exist_ok=True)
        name = "".join(c if c.isalnum() else "-" for c in self.title.lower()).strip("-") or "build"
        path = OUT / f"{name}.{fmt}"
        try:
            shapes = self._ev.step(self._program)
            if fmt == "stl" and any(isinstance(s.manifold, RawMesh) for s in shapes):
                raise ValueError("imported pieces that are not watertight cannot go to STL")
            exporter.export(shapes, self._program.get("materials", {}), path)
            self._say(f"exported {path}")
            return str(path)
        except (ValueError, EvalError) as e:
            self._say(f"export failed: {e}")
            return ""

    @Slot(str)
    def renderShowcase(self, camera_json: str):
        """Path-traced still from the current camera: Blender Cycles on the CPU (no GPU), OIDN denoised."""
        if not self._program:
            return
        from ..core import render
        cam = json.loads(camera_json)
        work = OUT / "renders"
        work.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        shapes = self._ev.step(self._program)
        glb = exporter.export(shapes, self._program.get("materials", {}), work / f"{stamp}.glb")
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
        work = OUT / "blender"
        work.mkdir(parents=True, exist_ok=True)
        shapes = self._ev.step(self._program)
        glb = exporter.export(shapes, self._program.get("materials", {}), work / time.strftime("%Y%m%d-%H%M%S.glb"))
        mats = self._program.get("materials", {})
        part_mats = {s.id: s.material for s in shapes if s.material}

        def job(log):
            if blender_link.is_up():
                raise RuntimeError("a Blender with the MCP socket is already open (localhost:9876); close it first")
            blender_link.open_in_blender(glb, mats, part_mats)
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
