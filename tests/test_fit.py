"""Fitting a build onto a printer bed (FR-PR-12 to FR-PR-14): the envelope, the never-clip gate, and
the fit functions. Every number is worked out by hand from the published bed sizes in core/printers.py
and the 2 mm safety margin (usable = bed - 4 on the bed plane, bed - 2 on the height), in the print
frame (Z up: X stays X, print Y is the program's Z, print Z is the program's Y-up height)."""
import json
from pathlib import Path

import pytest

from replicator import config
from replicator.core import export, fit, printers
from replicator.core.evaluate import Evaluator
from replicator.core.program import check

FIX = Path(__file__).parent.parent / "fixtures"
A1 = printers.CATALOG["bambu_a1"]          # 256 x 256 x 256 -> usable 252 x 252 x 254
X1C = printers.CATALOG["bambu_x1c"]        # 256 x 256 x 256 -> usable 252 x 252 x 254
A1_MINI = printers.CATALOG["bambu_a1_mini"]  # 180 x 180 x 180 -> usable 176 x 176 x 178


def _shapes(x, y, z, units="mm"):
    prog = check({"version": 1, "name": "box", "units": units,
                  "ops": [{"id": "box", "op": "box", "params": {"size": [x, y, z], "center": True}}]})
    return Evaluator().step(prog)


def test_oversize_box_is_refused_per_axis_and_scales_to_the_bed():
    # 300 x 100 x 50, Y up (300 along X, 100 tall, 50 along Z) -> print frame (300, 50, 100)
    shapes = _shapes(300, 100, 50)
    f = fit.check(shapes, "mm", A1)
    assert f.fits is False
    assert f.size == pytest.approx((300.0, 50.0, 100.0))
    assert f.overflow == pytest.approx((48.0, 0.0, 0.0), abs=1e-6)     # only X: 300 - 252
    assert f.clearance == pytest.approx((0.0, 202.0, 154.0), abs=1e-6)

    # no rotation helps at scale 1: 300 fits no axis of a 254 mm tall bed
    b = fit.best_orientation(shapes, "mm", A1)
    assert b.fits is False
    assert sum(b.overflow) == pytest.approx(46.0, abs=1e-6)            # standing it on end overflows least

    # upright, as built, the 300 axis takes the 252 bed axis
    t = fit.scale_to_fit(shapes, "mm", A1)
    assert t.fits and t.orientation == "as built"
    assert t.scale == pytest.approx(252 / 300, abs=1e-6)
    assert max(t.size) == pytest.approx(252.0, abs=1e-6)


def test_in_bed_box_reports_clearance_in_the_print_frame():
    # 200 x 50 x 20, Y up -> print frame (200, 20, 50)
    f = fit.check(_shapes(200, 50, 20), "mm", X1C)
    assert f.fits
    assert f.size == pytest.approx((200.0, 20.0, 50.0))
    assert f.clearance == pytest.approx((252 - 200, 252 - 20, 254 - 50))   # (52, 232, 204)
    assert f.overflow == (0.0, 0.0, 0.0)


def test_program_units_are_converted_before_fitting():
    f = fit.check(_shapes(30, 10, 5, units="cm"), "cm", A1)
    assert f.overflow == pytest.approx((48.0, 0.0, 0.0), abs=1e-6)       # the same 300 mm box
    assert fit.scale_to_fit(_shapes(30, 10, 5, units="cm"), "cm", A1).scale == pytest.approx(252 / 300, abs=1e-6)


def test_export_refuses_an_oversize_build_and_names_the_overflow(tmp_path):
    shapes = _shapes(300, 100, 50)
    with pytest.raises(ValueError) as e:
        export.export(shapes, {}, tmp_path / "box.stl", printer=A1)
    msg = str(e.value)
    assert A1.name in msg and "X" in msg and "48.0" in msg and "0.84" in msg
    assert not (tmp_path / "box.stl").exists()                            # refused before anything is written
    # nothing changes without a printer, and a build that fits passes the gate
    assert export.export(shapes, {}, tmp_path / "nogate.stl").exists()
    assert export.export(_shapes(200, 50, 20), {}, tmp_path / "ok.stl", printer=X1C).exists()


def test_replica_presets_scale_by_the_preset_rule():
    tall = _shapes(10, 240, 10)                                           # 240 mm tall in print Z
    assert fit.replica_scale("1:1", tall, "mm", A1) == 1.0
    assert fit.replica_scale("1:2", tall, "mm", A1) == pytest.approx(0.5)
    assert fit.replica_scale("height:120", tall, "mm", A1) == pytest.approx(0.5, abs=1e-9)
    f = fit.replica_scale("fit", _shapes(300, 100, 50), "mm", A1)
    assert f == pytest.approx(252 / 300, abs=1e-6)
    with pytest.raises(ValueError):
        fit.replica_scale("1:xx", tall, "mm", A1)
    with pytest.raises(ValueError):
        fit.replica_scale("height:-5", tall, "mm", A1)


def test_scale_for_printer_writes_a_house_that_fits_the_a1_mini(tmp_path):
    pytest.importorskip("mcp")
    from replicator import mcp_server as M
    out = str(tmp_path / "house_a1mini.json")
    r = M.scale_for_printer(str(FIX / "house_two_bed.json"), out, printer_id="bambu_a1_mini")
    assert r["ok"], r
    assert r["factor"] < 0.02                                             # an 11.9 m house onto a 176 mm bed
    assert (tmp_path / "house_a1mini.json").exists()

    # the written file is the source of truth: rebuild it and check it again
    prog = check(json.loads((tmp_path / "house_a1mini.json").read_text()))
    f = fit.check(Evaluator(tmp_path).step(prog), "mm", A1_MINI)
    assert f.fits and f.overflow == (0.0, 0.0, 0.0)
    assert r["size"] == pytest.approx(list(f.size), abs=1e-6)

    # a preset too big is refused with nothing written
    miss = str(tmp_path / "too_big.json")
    bad = M.scale_for_printer(str(FIX / "house_two_bed.json"), miss, printer_id="bambu_a1_mini",
                              preset="height:300")
    assert not bad["ok"] and "overflow" in bad["error"]
    assert not (tmp_path / "too_big.json").exists()


def test_printer_settings_round_trip_the_services_file(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PATH", tmp_path / "services.json")
    cfg = config.load()
    assert cfg["printers"] == [] and cfg["active_printer"] == ""
    cfg["printers"] = ["bambu_a1", {"id": "lab_a1", "name": "Lab A1", "vendor": "Lab",
                                     "bed_x": 200, "bed_y": 200, "height": 200}]
    cfg["active_printer"] = "lab_a1"
    config.save(cfg)

    again = config.load()
    assert again["printers"] == cfg["printers"] and again["active_printer"] == "lab_a1"
    assert [p.id for p in printers.configured(again)] == ["bambu_a1", "lab_a1"]
    assert printers.active(again).name == "Lab A1"
    assert printers.active({"active_printer": "bambu_a1", "printers": []}).id == "bambu_a1"
    assert printers.active({"active_printer": "", "printers": []}) is None
    assert printers.active({"active_printer": "no_such_bed", "printers": []}) is None


def test_catalog_and_dict_shapes():
    assert A1_MINI.usable() == (176.0, 176.0, 178.0)
    p = printers.Printer.from_dict({"id": "lab", "name": "Lab", "vendor": "Lab",
                                    "bed_x": 300, "bed_y": 200, "height": 400})
    assert p.nozzle == 0.4 and p.margin == 2.0 and p.transport == "file"
    assert p.usable() == (296.0, 196.0, 398.0)
    assert printers.CATALOG["bambu_h2d"].bed_x == 350
    with pytest.raises(ValueError):
        printers.Printer.from_dict({"id": "x"})
    with pytest.raises(ValueError):
        printers.Printer.from_dict({"id": "x", "name": "x", "vendor": "x",
                                    "bed_x": 10, "bed_y": 10, "height": 10, "margin": 6})   # margin eats the bed


def test_a_scaled_replica_keeps_its_plan_in_step():
    import json
    from pathlib import Path
    from replicator.core import assembly, critique
    from replicator.core.evaluate import Evaluator
    from replicator.core.program import check, scale_program
    fix = Path(__file__).parent.parent / "fixtures"
    prog = check(json.loads((fix / "rocket_engine.json").read_text()))
    small = scale_program(prog, 0.1)
    assert small["blueprint"]["dimensions"] == [v * 0.1 for v in prog["blueprint"]["dimensions"]]
    shapes = Evaluator(fix).step(small)
    assert not [i for i in critique.critique(small, shapes, assembly.components(small, shapes)) if i.kind == "size"]
