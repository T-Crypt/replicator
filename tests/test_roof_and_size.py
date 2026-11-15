"""The roof check (buildings) and the tiered size check, on a small synthetic house: 10 x 8 m walls, 2.75 m tops."""
import copy

import pytest

from replicator.core import assembly, critique
from replicator.core.evaluate import Evaluator
from replicator.core.program import check

WALLS = [
    {"id": "slab", "op": "box", "label": "Slab", "params": {"size": [10400, 150, 8400], "translate": [0, 75, 0]}},
    {"id": "wf", "op": "box", "label": "Front Wall", "params": {"size": [10000, 2600, 200], "translate": [0, 1450, 3900]}},
    {"id": "wb", "op": "box", "label": "Back Wall", "params": {"size": [10000, 2600, 200], "translate": [0, 1450, -3900]}},
    {"id": "wl", "op": "box", "label": "Left Wall", "params": {"size": [200, 2600, 8000], "translate": [-4900, 1450, 0]}},
    {"id": "wr", "op": "box", "label": "Right Wall", "params": {"size": [200, 2600, 8000], "translate": [4900, 1450, 0]}},
]


def house(panel: dict, plane=(0, 0, 1), summary="A house with a 30° pitched gable roof.") -> dict:
    """Two roof panels: `panel` and its mirror. The good gable has its ridge along X, 30 deg across Z."""
    roof = [{"id": "roof_panel", "op": "box", "label": "Roof Panel", "params": panel},
            {"id": "roof", "op": "array", "input": "roof_panel", "label": "Roof",
             "params": {"mode": "mirror", "count": 2, "plane": list(plane)}}]
    return {"version": 1, "name": "House", "units": "mm", "materials": {},
            "blueprint": {"summary": summary, "dimensions": [10900, 5100, 8900]}, "ops": copy.deepcopy(WALLS) + roof}


GOOD = {"size": [10900, 60, 5138], "rotate": [30, 0, 0], "translate": [0, 3805, 2225]}


def issues(prog: dict, tmp_path) -> list:
    prog = check(prog)
    shapes = Evaluator(tmp_path).step(prog)
    return critique.critique(prog, shapes, assembly.components(prog, shapes))


def kinds(found, kind):
    return [i for i in found if i.kind == kind]


def test_a_good_gable_passes(tmp_path):
    assert not kinds(issues(house(GOOD), tmp_path), "roof")


def test_a_v_roof_is_sent_back(tmp_path):
    v = dict(GOOD, rotate=[-30, 0, 0], translate=[0, 3805, 2225])        # slopes rise toward the eaves
    found = kinds(issues(house(v), tmp_path), "roof")
    assert found and found[0].severity == "fix" and "V" in found[0].message


def test_a_roof_that_leaves_walls_bare_is_sent_back(tmp_path):
    short = dict(GOOD, size=[6000, 60, 5138])                           # 6 m of roof over 10 m of walls
    found = kinds(issues(house(short), tmp_path), "roof")
    assert found and "uncovered" in found[0].message


def test_a_flat_roof_where_the_plan_wants_a_pitch(tmp_path):
    flat = {"size": [10900, 60, 4450], "translate": [0, 2780, 2225]}
    found = kinds(issues(house(flat), tmp_path), "roof")
    assert found and "flat" in found[0].message
    assert not kinds(issues(house(flat, summary="A house with a flat roof."), tmp_path), "roof")


def test_a_roof_inside_the_rooms(tmp_path):
    low = dict(GOOD, translate=[0, 2300, 2225])
    found = kinds(issues(house(low), tmp_path), "roof")
    assert found and "into the rooms" in found[0].message


def test_a_pitch_far_from_the_plan_is_shown(tmp_path):
    found = kinds(issues(house(GOOD, summary="A house with a 55° pitched gable roof."), tmp_path), "roof")
    assert found and found[0].severity == "warn" and "55" in found[0].message


def test_machines_are_left_alone(tmp_path):
    prog = {"version": 1, "name": "Bracket", "units": "mm", "materials": {},
            "ops": [{"id": "roof", "op": "box", "label": "Roof Plate", "params": {"size": [60, 6, 40]}}]}
    assert not kinds(issues(prog, tmp_path), "roof")


@pytest.mark.parametrize("height, severity", [(5100, None), (6200, "warn"), (8000, "fix")])
def test_size_warns_past_15_and_blocks_past_40_percent(tmp_path, height, severity):
    prog = house(GOOD)
    prog["blueprint"]["dimensions"] = [10900, 5100 * 5100 / height, 8900]   # same build, a smaller plan
    found = kinds(issues(prog, tmp_path), "size")
    assert (found[0].severity if found else None) == severity
