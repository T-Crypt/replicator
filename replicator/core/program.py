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
    "cylinder": ({"height", "radius"}, {"radius_top", "segments"}),
    "sphere": ({"radius"}, {"segments"}),
    "torus": ({"major_radius", "minor_radius"}, {"segments"}),
    "capsule": ({"height", "radius"}, {"segments"}),
    "extrude": ({"points", "height"}, {"axis", "twist", "scale_top", "holes"}),
    "revolve": ({"points"}, {"degrees", "segments"}),
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
OP_KEYS = {"id", "op", "label", "part", "params", "material", "input", "inputs"} | PLACEMENT
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


def normalize(program: dict) -> dict:
    """Models (and people) put translate/rotate/scale beside params as often as inside it. Move them in, in place."""
    for op in program.get("ops") or []:
        if not isinstance(op, dict):
            continue
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
