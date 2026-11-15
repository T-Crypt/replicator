import json
from pathlib import Path

import pytest

from replicator.core import dxf
from replicator.core.evaluate import Evaluator
from replicator.core.program import check

FIX = Path(__file__).parent.parent / "fixtures"
PLATE = {"version": 1, "name": "Plate", "units": "mm", "materials": {},
         "ops": [{"id": "p", "op": "box", "params": {"size": [120, 8, 60], "translate": [0, 4, 0]}},
                 {"id": "h", "op": "cylinder", "params": {"radius": 10, "height": 20, "translate": [0, 4, 0]}},
                 {"id": "plate", "op": "boolean", "inputs": ["p", "h"], "params": {"mode": "difference"}}]}


def _build(program):
    program = check(json.loads(json.dumps(program)))
    return Evaluator().step(program)


def _lines(ents, layer):
    return [e for e in ents if e[0] == "LINE" and e[1] == layer]


def test_the_front_view_is_full_size_at_the_origin():
    ents = dxf.entities(_build(PLATE))
    front = [e for e in _lines(ents, "OUTLINE") if max(e[2], e[4]) <= 120 + 1e-6 and max(e[3], e[5]) <= 8 + 1e-6]
    assert max(max(e[2], e[4]) for e in front) == pytest.approx(120)
    assert max(max(e[3], e[5]) for e in front) == pytest.approx(8)
    assert {e[5] for e in ents if e[0] == "TEXT" and e[1] == "DIMS"} == {"120", "8", "60"}


def test_the_section_shows_the_hole_as_a_gap_in_the_cut():
    ents = dxf.entities(_build(PLATE))
    titles = {e[5] for e in ents if e[0] == "TEXT" and e[1] == "TEXT"}
    assert titles == {"TOP", "FRONT", "RIGHT", "SECTION A-A"}
    cut = _lines(ents, "SECTION")
    xs = sorted({round(v, 3) for e in cut for v in (e[2], e[4])})
    left = min(xs)
    assert [round(x - left, 3) for x in xs] == [0.0, 50.0, 70.0, 120.0]     # 120 wide, a 20 mm hole in the middle


def test_a_building_gets_a_floor_plan_and_the_file_is_well_formed(tmp_path):
    program = json.loads((FIX / "house_two_bed.json").read_text())
    shapes = _build(program)
    f = dxf.write(shapes, tmp_path / "house.dxf")
    text = f.read_text()
    assert text.startswith("0\nSECTION\n2\nHEADER\n9\n$ACADVER\n1\nAC1009\n") and text.endswith("0\nEOF\n")
    for layer in dxf.LAYERS:
        assert f"\n8\n{layer}\n" in text
    assert "PLAN  (CUT AT 1200 mm)" in text


def test_ezdxf_reads_it_without_errors(tmp_path):
    ezdxf = pytest.importorskip("ezdxf")
    shapes = _build(PLATE)
    doc = ezdxf.readfile(dxf.write(shapes, tmp_path / "plate.dxf"))
    assert not doc.audit().errors
    assert {l.dxf.name for l in doc.layers} >= set(dxf.LAYERS)
