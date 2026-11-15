import json
import re
from pathlib import Path

from replicator.core import assembly, drawing, physics
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


def test_a_light_effect_has_no_mass_and_reads_as_one_in_the_parts_list():
    assert physics.density("glow") == ("effect", 0.0, True)
    assert physics.density("glow_titanium")[0] == "titanium"          # a named substance wins over the effect
    assert physics.density("emissive_led")[0] == "led"                # an LED is a real part
    p = json.loads((FIX / "vector_engine.json").read_text())
    shapes = Evaluator().step(p)
    m = physics.properties(p, shapes)
    assert "nozzle" not in m.by_component and m.kg > 0
    assert drawing._material_cell(["glow"]) == "light effect"
    assert drawing._material_cell(["titanium", "glow", "titanium"]) == "titanium"
    assert drawing._material_cell(["titanium", "ceramic"]) == "mixed"
    svg = drawing.sheet_svg(p, shapes, assembly.components(p, shapes))
    assert ">light effect<" in svg and ">glow<" not in svg


def test_the_svg_font_is_a_portable_list_qt_gets_one_installed_family():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    QGuiApplication.instance() or QGuiApplication([])
    from replicator.qt.svg import _one_family
    assert drawing.FONT.endswith("sans-serif") and "Mono" not in drawing.FONT
    have = QFontDatabase.families()
    assert _one_family("'Nowhere Sans', " + drawing.FONT) in have
    assert _one_family("'Nowhere Sans', Nowhere2") in have


def test_electronics_and_liquid_cooling_materials_have_real_densities():
    assert physics.density("pcb_green")[1] == 1850
    assert physics.density("acrylic_tube")[1] == 1180
    assert physics.density("glowing_coolant") == ("coolant", 1050, True)   # coolant is matter, even when it glows
    assert physics.density("silicon_die")[1] == 2330
