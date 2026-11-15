"""Replicator as an MCP server: any agent (Claude Code, Codex, Cursor, a lab's own harness) can read, edit, build, check,
draw and export a BuildProgram, and ask the local models to specify a new one.

    .venv/bin/python -m replicator.mcp_server            # stdio, for an agent's MCP config

The document is a program file on disk. Every write is validated and built before it replaces the file, so an agent
can never leave a broken program behind; the previous version is kept beside it as <name>.prev.json. A Replicator
window that has the same file open reloads it on change, so the timeline shows the agent's edits as they land.
Nothing here opens a GPU context: building, checks, drawings and STEP run on the CPU.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")           # a GPU is left to the model server

from mcp.server import MCPServer  # noqa: E402

from . import config  # noqa: E402
from .core import assembly, critique, fit, physics  # noqa: E402
from .core import printers as printers_mod  # noqa: E402 (the `printers` tool name takes the bare one)
from .core import export as exporter  # noqa: E402
from .core.evaluate import EvalError, Evaluator, bounds  # noqa: E402
from .core.program import ProgramError, apply_patch, check, scale_program  # noqa: E402

mcp = MCPServer("replicator", instructions=(
    "Replicator builds physical things from a BuildProgram: a JSON document of typed ops (primitives, modifiers, "
    "combiners, placement, engineering ops such as nozzle, rotor, wing, gear) evaluated into exact solids. "
    "It covers houses and floor plans, electronics, household objects, engines, aircraft and concepts. "
    "Start with `op_reference`, read a program with `read_program`, change it with `patch_program` (RFC 6902 JSON "
    "Patch; rejected patches leave the file untouched), and confirm with `build_report`, which returns size, mass, "
    "parts and every accuracy issue. `specify` asks the local models for a new program from a description. "
    "To print: `printers` lists the catalog and the active bed, `fit_check` measures a build against a bed and "
    "suggests the scale and orientation that fit, and `scale_for_printer` writes a scaled copy of the program that "
    "fits the bed. Nothing is ever clipped: an oversized print is refused with the overflow per axis."))


def _path(p: str) -> Path:
    return Path(p).expanduser().resolve()


def _report(program: dict, root: Path, step: int = -1) -> dict:
    t0 = time.perf_counter()
    prog = dict(program, ops=program["ops"][: step + 1]) if step >= 0 else program
    shapes = Evaluator(root).step(prog)
    ms = (time.perf_counter() - t0) * 1000
    comps = assembly.components(prog, shapes)
    mass = physics.properties(prog, shapes)
    issues = critique.critique(prog, shapes, comps)
    lo, hi = bounds(shapes) if shapes else ([0, 0, 0], [0, 0, 0])
    return {
        "name": prog.get("name", ""), "units": prog.get("units", "mm"), "ops": len(prog["ops"]),
        "total_ops": len(program["ops"]), "parts": len(shapes), "build_ms": round(ms),
        "size": [round(float(hi[i] - lo[i]), 3) for i in range(3)],
        "mass_kg": round(mass.kg, 4), "mass_assumed": mass.assumed,
        "components": [{"id": c.id, "label": c.label, "parts": len(c.shapes)} for c in comps],
        "issues": [i.as_dict() for i in issues],
        "blocking": len(critique.blocking(issues)),
    }


def _load(path: Path) -> dict:
    return check(json.loads(path.read_text()))


def _commit(path: Path, program: dict) -> dict:
    """Validate and build, then write atomically, keeping the old file as .prev.json."""
    program = check(program)
    report = _report(program, path.parent)
    if path.exists():
        path.with_suffix(".prev.json").write_text(path.read_text())
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(program, indent=1))
    tmp.replace(path)
    return report


def _err(e: Exception) -> dict:
    return {"ok": False, "error": f"{type(e).__name__}: {e}"}


@mcp.tool()
def op_reference() -> str:
    """The BuildProgram op vocabulary: every op, its kind, and its required and optional fields."""
    from .llm.client import op_reference as ref
    return ('Program: {"version": 1, "name": str, "units": "mm", "materials": {name: {"base_color": [r,g,b], '
            '"metalness", "roughness", "opacity"}}, "ops": [op, ...]}. Y is up.\n'
            'Op: {"id": str, "op": kind, "label": str, "part": str, "component": str, "material": name, '
            '"params": {...the fields below, plus "translate": [x,y,z], "rotate": [deg,deg,deg], "scale"}, '
            '"input": id (modifiers) or "inputs": [ids] (combiners)}. A consumed input stops being visible.\n'
            'Example: {"id": "boss", "op": "cylinder", "material": "alu", "params": {"radius": 17, "height": 3, '
            '"translate": [81, 24.5, 81]}}\n\n' + ref())


@mcp.tool()
def read_program(path: str) -> dict:
    """Read a BuildProgram file (validated)."""
    try:
        return {"ok": True, "program": _load(_path(path))}
    except (OSError, json.JSONDecodeError, ProgramError) as e:
        return _err(e)


@mcp.tool()
def write_program(path: str, program: dict) -> dict:
    """Create or replace a BuildProgram file. Rejected (file untouched) unless it validates and builds."""
    try:
        p = _path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        return {"ok": True, "report": _commit(p, program)}
    except (OSError, ProgramError, EvalError, ValueError) as e:
        return _err(e)


@mcp.tool()
def patch_program(path: str, patch: list[dict]) -> dict:
    """Apply an RFC 6902 JSON Patch to a program, e.g. [{"op": "replace", "path": "/ops/3/radius", "value": 12}].
    Rejected (file untouched) unless the result validates and builds; returns the new build report."""
    try:
        p = _path(path)
        return {"ok": True, "report": _commit(p, apply_patch(_load(p), patch))}
    except (OSError, json.JSONDecodeError, ProgramError, EvalError, ValueError) as e:
        return _err(e)


@mcp.tool()
def build_report(path: str, step: int = -1) -> dict:
    """Build a program (or only ops 0..step) and report size, mass, components and every accuracy issue.
    `blocking` > 0 means a check found something that must be fixed."""
    try:
        p = _path(path)
        return {"ok": True, "report": _report(_load(p), p.parent, step)}
    except (OSError, json.JSONDecodeError, ProgramError, EvalError) as e:
        return _err(e)


@mcp.tool()
def export(path: str, out: str) -> dict:
    """Export a program's solids. Format from the extension: .step/.stp (faceted B-rep for CAD), .stl and .3mf
    (printers, Z-up, watertight only), .glb, .obj."""
    try:
        p, o = _path(path), _path(out)
        program = _load(p)
        o.parent.mkdir(parents=True, exist_ok=True)
        shapes = Evaluator(p.parent).step(program)
        exporter.export(shapes, program.get("materials", {}), o, name=program.get("name", p.stem),
                        units=program.get("units", "mm"))
        return {"ok": True, "file": str(o), "bytes": o.stat().st_size}
    except (OSError, json.JSONDecodeError, ProgramError, EvalError, ValueError) as e:
        return _err(e)


def _printer(printer_id: str, cfg: dict):
    """Named printer (catalog, then saved profiles), else the active one. Raises when none is usable."""
    if printer_id:
        if printer_id in printers_mod.CATALOG:
            return printers_mod.CATALOG[printer_id]
        for p in printers_mod.configured(cfg):
            if p.id == printer_id:
                return p
        raise ValueError(f"printer {printer_id!r} is not in the catalog or saved profiles (see `printers`)")
    p = printers_mod.active(cfg)
    if p is None:
        raise ValueError("no printer: pass printer_id (see `printers`) or set active_printer in services.json")
    return p


def _fit_fields(f) -> dict:
    return {"fits": f.fits, "scale": f.scale, "orientation": f.orientation, "size": list(f.size),
            "usable": list(f.usable), "clearance": list(f.clearance), "overflow": list(f.overflow)}


@mcp.tool()
def printers() -> dict:
    """The printer catalog (Bambu Lab models, published build volumes to verify on the device), the
    profiles saved in services.json, and the active printer with its usable build volume."""
    try:
        cfg = config.load()
        active = printers_mod.active(cfg)
        return {"ok": True,
                "catalog": [p.as_dict() for p in printers_mod.CATALOG.values()],
                "saved": [p.as_dict() for p in printers_mod.configured(cfg)],
                "active": active.as_dict() if active else None}
    except (OSError, ValueError) as e:
        return _err(e)


@mcp.tool()
def fit_check(path: str, printer_id: str = "", scale: float = 1.0) -> dict:
    """Does the build fit the printer's bed (active printer when printer_id is empty)? Size in the
    print frame (Z up, mm), clearance or overflow per axis, plus the best orientation at scale 1 and
    the largest scale that fits."""
    try:
        p = _path(path)
        program = _load(p)
        shapes = Evaluator(p.parent).step(program)
        units = program.get("units", "mm")
        printer = _printer(printer_id, config.load())
        f = fit.check(shapes, units, printer, scale=scale)
        return {"ok": True, "printer": printer.id, "name": printer.name, "scale": scale,
                **_fit_fields(f),
                "best_orientation": _fit_fields(fit.best_orientation(shapes, units, printer)),
                "scale_to_fit": _fit_fields(fit.scale_to_fit(shapes, units, printer))}
    except (OSError, json.JSONDecodeError, ProgramError, EvalError, ValueError) as e:
        return _err(e)


@mcp.tool()
def scale_for_printer(path: str, out: str, printer_id: str = "", preset: str = "fit") -> dict:
    """Write `out` as a scaled copy of the program sized for the printer (active when printer_id is
    empty). preset: 1:1, 1:<n>, fit (largest factor the as-built build takes on the bed) or height:<mm>.
    Rejected (nothing written) unless the scaled build passes the fit check; returns the factor and
    the final print-frame size."""
    try:
        p, o = _path(path), _path(out)
        program = _load(p)
        shapes = Evaluator(p.parent).step(program)
        units = program.get("units", "mm")
        printer = _printer(printer_id, config.load())
        factor = fit.replica_scale(preset, shapes, units, printer)
        scaled = scale_program(program, factor)
        f = fit.check(Evaluator(o.parent).step(scaled), units, printer)
        if not f.fits:
            over = ", ".join(f"{ax} by {v:.1f} mm" for ax, v in zip(fit.AXES, f.overflow) if v > 0)
            raise ValueError(f"{printer.name} ({printer.id}): the {preset} build still overflows {over}; "
                             f"use a smaller preset or a bigger bed")
        o.parent.mkdir(parents=True, exist_ok=True)
        o.write_text(json.dumps(scaled, indent=1))
        return {"ok": True, "file": str(o), "printer": printer.id, "factor": factor,
                "size": list(f.size), "orientation": f.orientation}
    except (OSError, json.JSONDecodeError, ProgramError, EvalError, ValueError) as e:
        return _err(e)


@mcp.tool()
def drawing_sheet(path: str, out_dir: str, style: str = "blueprint") -> dict:
    """Draw an A3 sheet: third-angle views, section or floor plan, measured dimensions, numbered parts list with
    computed masses. Writes SVG and PNG. style: blueprint or paper."""
    try:
        from tools.sheet import make
    except ImportError:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
        from tools.sheet import make
    try:
        svg, png, seconds = make(_path(path), _path(out_dir), style)
        return {"ok": True, "svg": str(svg), "png": str(png), "seconds": round(seconds, 2)}
    except (OSError, json.JSONDecodeError, ProgramError, EvalError, ValueError) as e:
        return _err(e)


@mcp.tool()
def specify(description: str, out: str, engine: str = "") -> dict:
    """Ask the local models for a new BuildProgram from a description (blueprint, program, repair and critique
    rounds; takes minutes). Writes it to `out` only if it validates and builds. engine: empty for the default
    (`default_engine` in services.json, else "local"), or any name `engines` lists."""
    from .llm import client
    log: list[str] = []
    try:
        program = client.dream(description, engine, log=log.append)
        return {"ok": True, "report": _commit(_path(out), program), "log": log[-20:]}
    except Exception as e:  # noqa: BLE001 - a model failure is reported to the agent, the server stays up
        return dict(_err(e), log=log[-20:])


@mcp.tool()
def engines() -> dict:
    """The model engines `specify` can use: name -> model and chat URL ("local" plus configured endpoints)."""
    from .llm import client
    return {k: {"model": m, "url": u, "needs_key": bool(env) and not env.startswith("?")} for k, (u, m, _, env) in client.engines().items()}


@mcp.tool()
def reverse(mesh: str, out: str) -> dict:
    """Take an existing model (STL, OBJ, GLB, STEP, IGES and ~25 more) apart into a BuildProgram of its pieces, with
    a ledger tagging every claim observed, inferred or unknown. Piece geometry goes to <out dir>/assets/."""
    from .core import reverse as rev
    try:
        o = _path(out)
        o.parent.mkdir(parents=True, exist_ok=True)
        program, report = rev.analyze_mesh(_path(mesh), o.parent)
        o.write_text(json.dumps(program, indent=1))
        return {"ok": True, "program": str(o), "report": report}
    except Exception as e:  # noqa: BLE001
        return _err(e)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
