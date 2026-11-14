"""BuildProgram: the one document every Replicator view edits.

A program is plain JSON:

    {"version": 1, "name": "...", "units": "mm",
     "materials": {"steel": {"base_color": [0.6, 0.62, 0.65], "metalness": 1.0, "roughness": 0.35}},
     "blueprint": {...free-form notes from the blueprint stage...},
     "ops": [ {"id": "body", "op": "cylinder", "label": "Main casing", "part": "casing",
               "params": {"height": 120, "radius": 30}, "material": "steel"}, ... ]}

Ops run in list order. Build step k is ops[0..k]. An op that a later op consumes (via `input`/`inputs`) is hidden
from step k onward, so a step shows the scene exactly as it stands after that operation.
Coordinates are Y-up (glTF and Qt Quick 3D), right-handed, in `units`.
"""
from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import jsonpatch

VERSION = 1
UNITS = ("mm", "cm", "m")

# op name -> (required params, optional params). The schema the LLM is constrained to is generated from this.
PRIMITIVES = {
    "box": ({"size"}, {"center"}),
    "cylinder": ({"height", "radius"}, {"radius_top", "segments", "center"}),
    "sphere": ({"radius"}, {"segments"}),
    "torus": ({"major_radius", "minor_radius"}, {"segments"}),
    "capsule": ({"height", "radius"}, {"segments", "center"}),
    "extrude": ({"points", "height"}, {"axis", "twist", "scale_top", "holes"}),
    "revolve": ({"points"}, {"degrees", "segments"}),
    "mesh": ({"asset"}, set()),  # imported geometry (reverse engineering): an .npz with V, F beside program.json
}
MODIFIERS = {  # take one input
    "transform": (set(), set()),
    "array": ({"mode", "count"}, {"offset", "axis", "angle", "plane"}),
    "smooth": (set(), {"levels", "sharp_angle"}),
    "round": ({"radius"}, {"segments"}),
    "shell": ({"thickness"}, set()),
}
COMBINERS = {  # take two or more inputs
    "boolean": ({"mode"}, set()),
    "hull": (set(), set()),
    "group": (set(), set()),
}
PLACEMENT = {"translate", "rotate", "scale"}  # allowed on every op, applied last
OPS = {**PRIMITIVES, **MODIFIERS, **COMBINERS}
OP_KEYS = {"id", "op", "label", "part", "component", "params", "material", "input", "inputs"} | PLACEMENT
BOOLEAN_MODES = ("union", "difference", "intersection")
ARRAY_MODES = ("linear", "radial", "mirror")


class ProgramError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def op_inputs(op: dict) -> list[str]:
    if "inputs" in op:
        return list(op["inputs"])
    if "input" in op:
        return [op["input"]]
    return []


def component_map(program: dict) -> dict[str, str]:
    """op id -> component id: its own `component`, else its first input's, else its `part`, else its id."""
    out: dict[str, str] = {}
    for op in program["ops"]:
        ins = op_inputs(op)
        out[op["id"]] = op.get("component") or (out.get(ins[0]) if ins else None) or op.get("part") or op["id"]
    return out


def component_ops(program: dict, cid: str) -> list[str]:
    comp = component_map(program)
    return [op["id"] for op in program["ops"] if comp[op["id"]] == cid]


def delete_component(program: dict, cid: str) -> dict:
    """A copy without the component's ops. Refused when an op outside it still consumes one of them."""
    gone = set(component_ops(program, cid))
    if not gone:
        raise ProgramError([f"no component {cid!r}"])
    kept = [op for op in program["ops"] if op["id"] not in gone]
    users = sorted({op["id"] for op in kept for i in op_inputs(op) if i in gone})
    if users:
        raise ProgramError([f"{', '.join(users)} still use parts of {cid}; delete or rework those first"])
    if not kept:
        raise ProgramError(["that is the last component; close the build instead"])
    return check(dict(copy.deepcopy(program), ops=copy.deepcopy(kept)))


def duplicate_component(program: dict, cid: str, offset: list[float]) -> tuple[dict, str]:
    """A copy with the component repeated beside itself under a new id; returns (program, new component id)."""
    src = component_ops(program, cid)
    if not src:
        raise ProgramError([f"no component {cid!r}"])
    taken = {op["id"] for op in program["ops"]} | set(component_map(program).values())
    n = 2
    while f"{cid}_{n}" in taken or any(f"{o}_{n}" in taken for o in src):
        n += 1
    new_cid, rename = f"{cid}_{n}", {o: f"{o}_{n}" for o in src}
    srcset = set(src)
    consumed = {i for op in program["ops"] if op["id"] in srcset for i in op_inputs(op)}
    out = copy.deepcopy(program)
    for op in [copy.deepcopy(o) for o in program["ops"] if o["id"] in srcset]:
        op["id"] = rename[op["id"]]
        op["component"] = new_cid
        if "input" in op:
            op["input"] = rename.get(op["input"], op["input"])
        if "inputs" in op:
            op["inputs"] = [rename.get(i, i) for i in op["inputs"]]
        if op["id"] not in {rename[c] for c in consumed if c in rename}:
            t = op.setdefault("params", {}).get("translate", [0, 0, 0])
            op["params"]["translate"] = [round(t[k] + offset[k], 3) for k in range(3)]
        if op.get("label"):
            op["label"] += " (copy)"
        out["ops"].append(op)
    comps = out.get("components")
    if isinstance(comps, list):
        meta = next((dict(c) for c in comps if c.get("id") == cid), {"id": cid})
        comps.append(dict(meta, id=new_cid, label=(meta.get("label") or cid) + " (copy)"))
    return check(out), new_cid


def normalize(program: dict) -> dict:
    """Models (and people) put translate/rotate/scale beside params as often as inside it. Move them in, in place."""
    for op in program.get("ops") or []:
        if not isinstance(op, dict):
            continue
        for k in ("input", "inputs"):            # local models write "input": null on primitives
            if k in op and op[k] in (None, "", []):
                del op[k]
        for k in PLACEMENT & op.keys():
            params = op.setdefault("params", {})
            if isinstance(params, dict):
                params.setdefault(k, op.pop(k))
    return program


def validate(program: dict) -> list[str]:
    """Every problem as a short sentence (fed back to the model on a repair round). Empty list = valid."""
    errs: list[str] = []
    normalize(program)
    if program.get("version") != VERSION:
        errs.append(f"version must be {VERSION}")
    if program.get("units", "mm") not in UNITS:
        errs.append(f"units must be one of {UNITS}")
    mats = program.get("materials", {})
    if not isinstance(mats, dict):
        errs.append("materials must be an object")
        mats = {}
    comps = program.get("components")
    comp_ids: set[str] | None = None
    if comps is not None:
        if not isinstance(comps, list) or not all(isinstance(c, dict) and c.get("id") for c in comps):
            errs.append("components must be a list of objects with an id")
        else:
            comp_ids = {c["id"] for c in comps}
    ops = program.get("ops")
    if not isinstance(ops, list) or not ops:
        return errs + ["ops must be a non-empty list"]
    seen: set[str] = set()
    for i, op in enumerate(ops):
        where = f"ops[{i}]"
        if not isinstance(op, dict):
            errs.append(f"{where} is not an object")
            continue
        oid, kind = op.get("id"), op.get("op")
        where = f"ops[{i}] ({oid})"
        if not isinstance(oid, str) or not oid:
            errs.append(f"{where}: id must be a non-empty string")
        elif oid in seen:
            errs.append(f"{where}: duplicate id")
        if kind not in OPS:
            errs.append(f"{where}: unknown op {kind!r}; use one of {sorted(OPS)}")
            seen.add(oid)
            continue
        unknown = op.keys() - OP_KEYS
        if unknown:
            errs.append(f"{where}: unknown keys {sorted(unknown)}; op keys are {sorted(OP_KEYS)}")
        params = op.get("params", {})
        if not isinstance(params, dict):
            errs.append(f"{where}: params must be an object")
            params = {}
        req, opt = OPS[kind]
        missing = req - params.keys()
        extra = params.keys() - req - opt - PLACEMENT
        if missing:
            errs.append(f"{where}: {kind} needs params {sorted(missing)}")
        if extra:
            errs.append(f"{where}: {kind} does not take params {sorted(extra)}")
        ins = op_inputs(op)
        for ref in ins:
            if ref not in seen:
                errs.append(f"{where}: input {ref!r} is not an earlier op id")
        if kind in PRIMITIVES and ins:
            errs.append(f"{where}: {kind} is a primitive and takes no input")
        if kind in MODIFIERS and len(ins) != 1:
            errs.append(f"{where}: {kind} takes exactly one input")
        if kind in COMBINERS and len(ins) < 2:
            errs.append(f"{where}: {kind} takes two or more inputs")
        if kind == "boolean" and params.get("mode") not in BOOLEAN_MODES:
            errs.append(f"{where}: boolean mode must be one of {BOOLEAN_MODES}")
        if kind == "array" and params.get("mode") not in ARRAY_MODES:
            errs.append(f"{where}: array mode must be one of {ARRAY_MODES}")
        comp = op.get("component")
        if comp is not None and comp_ids is not None and comp not in comp_ids:
            errs.append(f"{where}: component {comp!r} is not in components")
        mat = op.get("material")
        if mat is not None and mat not in mats:
            errs.append(f"{where}: material {mat!r} is not defined in materials")
        seen.add(oid)
    return errs


def check(program: dict) -> dict:
    errs = validate(program)
    if errs:
        raise ProgramError(errs)
    return program


def register(primitives: dict, modifiers: dict) -> None:
    """Add op families from an extension module (name -> (required, optional, builder)) to the schema."""
    for table, ext in ((PRIMITIVES, primitives), (MODIFIERS, modifiers)):
        for name, (req, opt, _fn) in ext.items():
            table[name] = (set(req), set(opt))
    OPS.clear()
    OPS.update({**PRIMITIVES, **MODIFIERS, **COMBINERS})


def op_hash(op: dict, input_hashes: list[str]) -> str:
    body = {k: op.get(k) for k in ("op", "params", "input", "inputs")}
    h = hashlib.sha256(json.dumps(body, sort_keys=True).encode())
    for ih in input_hashes:
        h.update(ih.encode())
    return h.hexdigest()[:16]


def apply_patch(program: dict, patch: list[dict]) -> dict:
    """An RFC 6902 patch from a text edit. Returns a new, validated program; the old one is untouched."""
    new = jsonpatch.apply_patch(copy.deepcopy(program), patch)
    return check(new)


@dataclass
class Project:
    """<name>.replicator/ on disk: program.json plus history/NNNN.json, one file per saved version."""
    root: Path

    @property
    def program_path(self) -> Path:
        return self.root / "program.json"

    def load(self) -> dict:
        return check(json.loads(self.program_path.read_text()))

    def save(self, program: dict, note: str = "") -> int:
        check(program)
        hist = self.root / "history"
        hist.mkdir(parents=True, exist_ok=True)
        n = len(list(hist.glob("*.json"))) + 1
        rec = {"note": note, "program": program}
        (hist / f"{n:04d}.json").write_text(json.dumps(rec, indent=1))
        self.program_path.write_text(json.dumps(program, indent=1))
        return n

    def version(self, n: int) -> dict:
        return json.loads((self.root / "history" / f"{n:04d}.json").read_text())["program"]
