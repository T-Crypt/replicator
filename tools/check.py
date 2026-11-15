"""Check a BuildProgram the way the workshop does: validate, build, measure, critique.

    .venv/bin/python -m tools.check replicator/fixtures/rocket_engine.json [more.json ...]

Prints size, parts, mass and every accuracy issue; exits 1 when any program is invalid or has a `fix` issue.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from replicator.core import assembly, critique, physics
from replicator.core.evaluate import EvalError, Evaluator, bounds
from replicator.core.program import ProgramError, check


def report(path: Path) -> bool:
    try:
        program = check(json.loads(path.read_text()))
        t0 = time.perf_counter()
        shapes = Evaluator(path.parent).step(program)
        ms = (time.perf_counter() - t0) * 1000
    except (OSError, json.JSONDecodeError, ProgramError, EvalError) as e:
        print(f"{path}: INVALID: {e}")
        return False
    lo, hi = bounds(shapes)
    comps = assembly.components(program, shapes)
    mass = physics.properties(program, shapes)
    issues = critique.critique(program, shapes, comps)
    size = " x ".join(f"{hi[i] - lo[i]:.0f}" for i in range(3))
    print(f"{path}: {len(program['ops'])} ops, {len(shapes)} parts, {len(comps)} components, {size} "
          f"{program.get('units', 'mm')}, {mass.kg:.2f} kg{' (some densities assumed)' if mass.assumed else ''}, "
          f"built in {ms:.0f} ms")
    for i in issues:
        print(f"  {i.severity.upper():4} {i.kind:9} {i.subject or '-'}: {i.message}")
    return not critique.blocking(issues)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    ok = [report(Path(p)) for p in sys.argv[1:]]
    sys.exit(0 if all(ok) else 1)
