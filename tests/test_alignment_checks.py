"""The three measured proportion checks: radial rings spun about the wrong axis, parts that do not run along the
part the plan says they run along, and shapes outside a knowledge card's stated rise range."""
import json
from pathlib import Path

import pytest

from replicator.core import assembly, critique
from replicator.core.evaluate import Evaluator
from replicator.core.program import check

ROOT = Path(__file__).parent.parent
FIX = ROOT / "fixtures"
DATA = Path(__file__).parent / "data"
NEW_KINDS = ("off_axis", "alignment", "proportion")


def issues(path: Path) -> list:
    prog = check(json.loads(path.read_text()))
    shapes = Evaluator(path.parent).step(prog)
    return critique.critique(prog, shapes, assembly.components(prog, shapes))


def kinds(found, kind):
    return [i for i in found if i.kind == kind]


def test_a_turbofan_ringing_around_the_wrong_axis_is_sent_back():
    # the shipped build also puts the fuel nozzles around world Y, so the third fix is the nozzle ring; the
    # turbine vane source sits in a gap no axisymmetric body covers, which the check reports as no body
    found = kinds(issues(DATA / "turbofan_wrong_axis.json"), "off_axis")
    assert len(found) == 3
    assert all(i.severity == "fix" for i in found)
    msgs = [i.message for i in found]
    assert any("Fan Blade Set" in m for m in msgs)
    assert any("Reverse Vane Ring" in m for m in msgs)
    assert any("Fuel Nozzle Ring" in m for m in msgs)


def test_a_correctly_ringed_engine_passes():
    assert not [i for i in issues(FIX / "turbofan.json") if i.kind in NEW_KINDS]


def test_a_flat_lamp_whose_springs_stand_straight_is_sent_back():
    found = issues(DATA / "desk_lamp_flat.json")
    align = kinds(found, "alignment")
    assert len(align) == 2
    assert all(i.severity == "fix" for i in align)
    msgs = [i.message for i in align]
    assert any("Lower Arm Spring" in m for m in msgs)
    assert any("Upper Arm Spring" in m for m in msgs)
    prop = kinds(found, "proportion")
    assert len(prop) == 2
    assert all(i.severity == "fix" for i in prop)
    msgs = [i.message for i in prop]
    assert any("Lower Aluminium Arm" in m for m in msgs)
    assert any("Upper Aluminium Arm" in m for m in msgs)


def ring(axis: str) -> dict:
    return {"version": 1, "name": "Ringed column", "units": "mm", "materials": {}, "ops": [
        {"id": "body", "op": "cylinder", "label": "Column", "params": {"radius": 50, "height": 200, "segments": 32}},
        {"id": "src", "op": "box", "label": "Vane Source", "params": {"size": [20, 20, 20], "translate": [60, 0, 0]}},
        {"id": "ring", "op": "array", "input": "src", "label": "Vane Ring",
         "params": {"mode": "radial", "count": 6, "axis": axis}}]}


def issues_prog(p: dict, tmp_path) -> list:
    prog = check(p)
    shapes = Evaluator(tmp_path).step(prog)
    return critique.critique(prog, shapes, assembly.components(prog, shapes))


def test_a_ring_that_spins_around_the_body_axis_passes(tmp_path):
    assert not kinds(issues_prog(ring("y"), tmp_path), "off_axis")


def test_a_ring_that_spins_sideways_is_sent_back(tmp_path):
    found = kinds(issues_prog(ring("x"), tmp_path), "off_axis")
    assert len(found) == 1
    assert found[0].severity == "fix" and "Column" in found[0].message


@pytest.mark.parametrize("name", sorted(p.name for p in FIX.glob("*.json")
                                        if p.name not in ("turbofan_bad.json", "advanced_ops.json")))
def test_no_other_fixture_trips_the_new_checks(name):
    assert not [i for i in issues(FIX / name) if i.kind in NEW_KINDS]
