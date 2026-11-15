"""Machine-verifiable corpus export of valid, built programs.

    .venv/bin/python -m tools.corpus export <file-or-dir>... -o corpus.jsonl
    .venv/bin/python -m tools.corpus verify corpus.jsonl

export validates and builds every program under the given paths (inside a `*.replicator/` folder only its
program.json, never history/) and writes one JSON object per surviving program. verify rebuilds every row
from its stored program and recomputes id, geometry and verdict; export and verify share one `row` function,
so a row that once verified cannot silently drift.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import sys
from pathlib import Path

from replicator.core import assembly, critique, physics
from replicator.core.evaluate import EvalError, Evaluator, RawMesh, bounds
from replicator.core.program import VERSION, ProgramError, check


def _digest16(canonical: str) -> str:
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def row(path: Path, program: dict) -> dict:
    """One corpus row, identical whether written by export or recomputed by verify. `path` names the program
    file: its parent is the project root mesh assets are loaded from (the cwd when the file is gone)."""
    base = path.parent if path.parent.is_dir() else Path.cwd()
    shapes = Evaluator(base).step(program)
    lo, hi = bounds(shapes)
    comps = assembly.components(program, shapes)
    mass = physics.properties(program, shapes)
    issues = critique.critique(program, shapes, comps)
    solids = [s for s in shapes if not isinstance(s.manifold, RawMesh)]
    # raw meshes count as parts but are not closed solids, so they stay out of volume and digest
    digest_in = sorted(([s.id, round(s.manifold.volume(), 2), [round(v, 2) for v in s.manifold.bounding_box()]]
                       for s in solids), key=lambda e: e[0])
    source = program.get("source")
    if not isinstance(source, dict):
        source = {}
    return {
        "id": _digest16(json.dumps(program, sort_keys=True, separators=(",", ":"))),
        "file": str(path),
        "prompt": source.get("prompt") or None,
        "engine": source.get("engine") or None,
        "program": program,
        "geometry": {
            "parts": len(shapes),
            "volume": round(sum(s.manifold.volume() for s in solids), 2),
            "size": [round(hi[i] - lo[i], 2) for i in range(3)],
            "digest": _digest16(json.dumps(digest_in, sort_keys=True, separators=(",", ":"))),
        },
        "mass_kg": round(mass.kg, 4),
        "mass_assumed": bool(mass.assumed),
        "verdict": {
            "blocking": len(critique.blocking(issues)),
            "issues": sorted(([[i.kind, i.severity, i.subject] for i in issues])),
        },
        "kernel": {
            "manifold3d": importlib.metadata.version("manifold3d"),
            "replicator_program_version": VERSION,
        },
    }


def _candidates(root: Path) -> list[Path]:
    """Every *.json under root; inside a `*.replicator/` folder only its own program.json."""
    out = []
    for f in sorted(root.rglob("*.json")):
        inside = [d for d in f.relative_to(root).parts[:-1] if d.endswith(".replicator")]
        if inside and not (f.parent.name.endswith(".replicator") and f.name == "program.json"):
            continue
        out.append(f)
    return out


def export(inputs: list[str], out: Path) -> int:
    inputs = [Path(p) for p in inputs]
    missing = [p for p in inputs if not p.exists()]
    if missing:
        for p in missing:
            print(f"error: {p} does not exist", file=sys.stderr)
        return 2
    cands: list[Path] = []
    for p in inputs:
        cands.extend([p] if p.is_file() else _candidates(p))
    seen: set[Path] = set()
    rows, skipped = [], 0
    for p in cands:
        key = p.resolve()
        if key in seen:
            continue
        seen.add(key)
        try:
            program = check(json.loads(p.read_text()))
        except (OSError, json.JSONDecodeError, ProgramError) as e:
            print(f"skip {p}: {e}")
            skipped += 1
            continue
        try:
            rows.append(row(p, program))
        except EvalError as e:
            print(f"skip {p}: {e}")
            skipped += 1
    text = "\n".join(json.dumps(r) for r in rows)
    if text:
        text += "\n"
    try:
        out.write_text(text)
    except OSError as e:
        print(f"error: cannot write {out}: {e}", file=sys.stderr)
        return 2
    print(f"{len(rows)} programs, {skipped} skipped -> {out}")
    return 0


def _kernel() -> dict:
    return {"manifold3d": importlib.metadata.version("manifold3d"),
            "replicator_program_version": VERSION}


def verify(corpus: Path) -> int:
    if not corpus.is_file():
        print(f"error: {corpus} does not exist", file=sys.stderr)
        return 2
    try:
        rows = [json.loads(line) for line in corpus.read_text().splitlines() if line.strip()]
    except json.JSONDecodeError as e:
        print(f"error: {corpus}: {e}", file=sys.stderr)
        return 2
    installed = _kernel()
    ok = 0
    for r in rows:
        rid, file = r.get("id"), r.get("file")
        if isinstance(r.get("kernel"), dict) and r["kernel"] != installed:
            print(f"note {rid} {file}: stored kernel {r['kernel']} differs from the installed {installed}")
        prog = r.get("program")
        if not isinstance(prog, dict):
            print(f"MISMATCH {rid} {file}: the row has no program")
            continue
        path = Path(file) if isinstance(file, str) and Path(file).parent.is_dir() else Path("program.json")
        try:
            fresh = row(path, prog)
        except (ProgramError, EvalError) as e:
            print(f"MISMATCH {rid} {file}: rebuild failed ({e})")
            continue
        bad = [k for k in ("id", "geometry", "verdict") if fresh[k] != r.get(k)]
        if bad:
            print(f"MISMATCH {rid} {file}: {', '.join(bad)}")
        else:
            ok += 1
            print(f"ok {rid} {file}")
    print(f"{ok}/{len(rows)} rows re-verify")
    return 0 if ok == len(rows) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools.corpus", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="write one JSON row per valid, built program")
    e.add_argument("inputs", nargs="+", metavar="file-or-dir")
    e.add_argument("-o", "--out", required=True)
    v = sub.add_parser("verify", help="rebuild every row and recompute id, geometry and verdict")
    v.add_argument("corpus")
    a = ap.parse_args(argv)
    if a.cmd == "export":
        return export(a.inputs, Path(a.out))
    return verify(Path(a.corpus))


if __name__ == "__main__":
    sys.exit(main())
