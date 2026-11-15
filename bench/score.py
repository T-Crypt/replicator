"""Score a BuildProgram against a task instance: build it once, measure it, grade the assertions.

An assertion is a record (kind, args, weight); each kind maps to a pure measure in MEASURES that
looks at the built solid and returns (passed, a short note of the observed value). Nothing here
talks to a model, so the same program and instance always give the same dict.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from replicator.core import assembly, critique, physics
from replicator.core.evaluate import Evaluator, RawMesh, Shape, bounds
from replicator.core.program import check

AXIS = {"x": 0, "y": 1, "z": 2}


@dataclass(frozen=True)
class Assertion:
    kind: str
    args: dict
    weight: float = 1.0
    label: str = ""


@dataclass(frozen=True)
class Instance:
    task: str
    seed: int
    prompt: str
    assertions: tuple[Assertion, ...]
    params: dict


@dataclass
class Built:
    program: dict
    shapes: list
    comps: list
    issues: list
    mass: object


def _solid(s: Shape) -> bool:
    return not isinstance(s, RawMesh)


def solids(built: Built) -> list:
    return [s for s in built.shapes if _solid(s)]


def _named(s, word: str) -> bool:
    word = word.lower()
    return word in f"{s.label} {s.part} {s.component}".lower()


def _shapes(built: Built, word: str | None) -> list:
    ss = solids(built)
    return ss if word is None else [s for s in ss if _named(s, word)]


def _extent(shapes, axis: str) -> float:
    lo, hi = bounds(shapes)
    a = AXIS[axis]
    return hi[a] - lo[a]


def m_size(built: Built, a: dict) -> tuple[bool, str]:
    axis = str(a["axis"]).lower()
    got = _extent(built.shapes, axis)
    target, tol = float(a["target"]), float(a["tol"])
    return abs(got - target) <= target * tol, f"{axis} {got:.1f} vs target {target:g}"


def m_size_range(built: Built, a: dict) -> tuple[bool, str]:
    axis = str(a["axis"]).lower()
    got = _extent(built.shapes, axis)
    lo, hi = float(a["min"]), float(a["max"])
    return lo <= got <= hi, f"{axis} {got:.1f} vs {lo:g}..{hi:g}"


def m_genus(built: Built, a: dict) -> tuple[bool, str]:
    total = sum(s.manifold.genus() for s in _shapes(built, a.get("word")))
    if "equals" in a:
        want, mode = int(a["equals"]), "="
    else:
        want, mode = int(a["min"]), ">="
    return (total == want if mode == "=" else total >= want), f"genus {total} vs {mode} {want}"


def m_volume(built: Built, a: dict) -> tuple[bool, str]:
    got = sum(s.manifold.volume() for s in _shapes(built, None))
    target, tol = float(a["target"]), float(a["tol"])
    return abs(got - target) <= target * tol, f"{got:.0f} vs target {target:.0f}"


def m_part(built: Built, a: dict) -> tuple[bool, str]:
    word = str(a["word"])
    hit = next((s.label or s.part or s.id for s in built.shapes if _named(s, word)), None)
    note = hit if hit else f"no shape named {word.lower()}"
    return hit is not None, note


def m_no_issues(built: Built, a: dict) -> tuple[bool, str]:
    kinds = set(a.get("kinds") or ())
    bad = sorted({i.kind for i in built.issues if i.kind in kinds})
    return not bad, (", ".join(bad) or "none")


def m_no_blocking(built: Built, a: dict) -> tuple[bool, str]:
    n = len(critique.blocking(built.issues))
    return n == 0, f"{n} blocking"


def m_floor_area(built: Built, a: dict) -> tuple[bool, str]:
    word = str(a["word"])
    ss = _shapes(built, word)
    if not ss:
        return False, f"no solid shape named {word.lower()}"
    m2 = _extent(ss, "x") * _extent(ss, "z") / 1e6
    want = float(a["min_m2"])
    return m2 >= want, f"{m2:.1f} m^2 vs >= {want:g}"


def m_top_of(built: Built, a: dict) -> tuple[bool, str]:
    word = str(a["word"])
    ss = _shapes(built, word)
    if not ss:
        return False, f"no solid shape named {word.lower()}"
    top = max(s.manifold.bounding_box()[4] for s in ss)
    lo, hi = float(a["min"]), float(a["max"])
    return lo <= top <= hi, f"top {top:.0f} vs {lo:g}..{hi:g}"


MEASURES: dict[str, Callable[[Built, dict], tuple[bool, str]]] = {
    "size": m_size,
    "size_range": m_size_range,
    "genus": m_genus,
    "volume": m_volume,
    "part": m_part,
    "no_issues": m_no_issues,
    "no_blocking": m_no_blocking,
    "floor_area": m_floor_area,
    "top_of": m_top_of,
}


def build(program: dict, root: Path | None) -> Built:
    """The workshop's whole pipeline once: shapes, components, mass and critique."""
    shapes = Evaluator(root).step(program)
    comps = assembly.components(program, shapes)
    mass = physics.properties(program, shapes)
    issues = critique.critique(program, shapes, comps)
    return Built(program, shapes, comps, issues, mass)


def score(program: dict, inst: Instance, root: Path | None = None) -> dict:
    """Gate: valid program, clean build, at least one solid shape. Then the weighted assertions
    and the blocking-issue discount. The result is plain JSON-able data, identical for identical
    inputs."""
    try:
        program = check(program)
    except Exception as e:  # noqa: BLE001 - any validation failure is a gate failure with the reason
        return {"score": 0.0, "gate": False, "reason": f"invalid program: {e}", "assertions": []}
    try:
        built = build(program, root)
    except Exception as e:  # noqa: BLE001 - a build that throws is a gate failure with the reason
        return {"score": 0.0, "gate": False, "reason": f"build failed: {e}", "assertions": []}
    if not solids(built):
        return {"score": 0.0, "gate": False, "reason": "the build has no solid shape", "assertions": []}
    rows = []
    got_w = total_w = 0.0
    for a in inst.assertions:
        try:
            ok, note = MEASURES[a.kind](built, a.args)
        except Exception as e:  # noqa: BLE001 - a measure that errors counts as a failed assertion
            ok, note = False, f"measure error: {e}"
        rows.append({"label": a.label or a.kind, "kind": a.kind, "passed": bool(ok), "observed": note})
        total_w += a.weight
        if ok:
            got_w += a.weight
    n_block = len(critique.blocking(built.issues))
    checks = 1.0 if n_block == 0 else max(0.0, 1.0 - 0.25 * n_block)
    a_score = got_w / total_w if total_w else 0.0
    return {"score": round(0.7 * a_score + 0.3 * checks, 4), "gate": True,
            "assertions": rows, "blocking": n_block}
