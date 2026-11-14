import json
import re
from pathlib import Path

from replicator.core import assembly, drawing
from replicator.core.evaluate import Evaluator

FIX = Path(__file__).parent.parent / "fixtures"


def sheet(program):
    shapes = Evaluator().step(program)
    return drawing.sheet_svg(program, shapes, assembly.components(program, shapes))


def test_engine_sheet_has_views_dimensions_callouts_and_parts_list():
    p = json.loads((FIX / "rocket_engine.json").read_text())
    svg = sheet(p)
    for title in ("TOP", "FRONT", "RIGHT", "SECTION A-A", "PARTS LIST", "1:15", "1070", "1830", "812"):
        assert f">{title}<" in svg
    assert len(re.findall(r'<circle [^>]*r="2.4"', svg)) == 11


def test_a_house_gets_a_floor_plan_cut_at_1200():
    walls = [{"id": f"w{i}", "op": "box", "component": "walls", "params": {"size": s, "translate": t}}
             for i, (s, t) in enumerate([([8000, 2700, 200], [0, 1350, -2900]), ([8000, 2700, 200], [0, 1350, 2900]),
                                         ([200, 2700, 6000], [-3900, 1350, 0]), ([200, 2700, 6000], [3900, 1350, 0])])]
    roof = {"id": "roof", "op": "box", "component": "roof", "params": {"size": [8400, 200, 6400], "translate": [0, 2800, 0]}}
    svg = sheet({"version": 1, "units": "mm", "ops": walls + [roof]})
    assert ">PLAN  (CUT AT 1200 mm)<" in svg and ">FRONT ELEVATION<" in svg and "SECTION A-A" not in svg
    assert 'fill-opacity="0.55"' in svg
