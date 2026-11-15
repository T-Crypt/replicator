import copy
import json
import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtGui import QGuiApplication  # noqa: E402

from replicator.qt import bridge  # noqa: E402

FIX = Path(__file__).parent.parent / "fixtures"


@pytest.fixture
def studio(tmp_path, monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(bridge, "OUT", tmp_path)
    s = bridge.Studio()
    s.openFile(str(FIX / "rocket_engine.json"))
    return s


def test_a_dream_that_lands_after_close_is_saved_not_shown(studio, tmp_path):
    finished = copy.deepcopy(studio._program)
    started = studio._epoch
    studio.closeProgram()
    studio._on_job({"program": finished, "epoch": started}, "done")
    assert studio._program is None
    assert len(list(tmp_path.glob("*.json"))) == 1


def test_an_agent_edit_on_an_older_version_is_dropped(studio):
    base = studio._program
    studio.duplicateComponent("gimbal")
    newer = studio._program
    studio._on_job({"program": copy.deepcopy(base), "base": base, "epoch": studio._epoch}, "done")
    assert studio._program is newer


def test_delete_is_one_undo_step_and_unknown_parts_are_refused(studio):
    before = studio._program
    studio.deleteComponent("turbopump")
    assert len(studio._program["ops"]) == len(before["ops"]) - 7
    studio.undo()
    assert studio._program is before
    studio.deleteComponent("no_such_part")
    assert "no component" in studio.lastLog and studio._program is before


def test_issues_and_mass_reach_qml_as_plain_values(studio):
    studio.waitMeasured()
    assert studio.issues == []
    m = studio.mass
    assert type(m["kg"]) is float and 300 < m["kg"] < 600
    json.dumps(m)


def test_export_never_overwrites_and_rejects_odd_formats(studio, tmp_path):
    a, b = studio.exportAs("glb"), studio.exportAs("glb")
    assert a != b and Path(a).exists() and Path(b).exists()
    assert studio.exportAs("glb/../../x") == ""


def test_measurement_is_off_the_edit_path_and_stale_results_are_ignored(studio):
    studio.waitMeasured()
    old = studio._program
    studio.deleteComponent("turbopump")
    assert studio.measuring
    kg_before = studio.mass["kg"]
    studio._on_measured(old, [{"severity": "fix", "message": "stale", "subject": ""}], studio._mass)
    assert studio.issues == []
    studio.waitMeasured()
    assert not studio.measuring and studio.mass["kg"] < kg_before


def test_selected_facts_carry_size_and_component_mass(studio):
    studio.waitMeasured()
    studio.select("gimbal")
    f = studio.selectedFacts
    assert len(f["size"]) == 3 and all(type(x) is float for x in f["size"])
    assert type(f.get("kg", 0.0)) is float


def test_new_engineering_params_get_typed_rows(studio):
    studio.addPrimitive("grille")
    rows = {r["key"]: r for r in studio.selectedParams}
    assert rows["hole"]["kind"] == "enum" and "slot" in rows["hole"]["options"]
    studio.addPrimitive("rotor")
    rows = {r["key"]: r for r in studio.selectedParams}
    assert rows["blades"]["integer"] and not rows["tip_radius"]["integer"]


def test_3mf_export_fails_with_a_message_not_an_exception(studio):
    out = studio.exportAs("3mf")
    assert out == "" or Path(out).exists()
    assert out or "export failed" in studio.lastLog


def test_sheet_job_writes_svg_and_png_and_a_new_build_closes_it(studio, tmp_path, monkeypatch):
    class Now:   # run the job inline so the result lands before the assert
        def __init__(self, target, daemon):
            self.target = target

        def start(self):
            self.target()
    monkeypatch.setattr(bridge.threading, "Thread", Now)
    studio.makeSheet("paper")
    sheet = studio.sheet
    assert sheet, "the sheet job reported a failure"
    assert Path(sheet["svg"]).read_text().startswith("<")
    assert Path(sheet["png"]).stat().st_size > 10_000
    assert Path(sheet["svg"]).parent == tmp_path / "sheets"
    studio.duplicateComponent("gimbal")
    assert studio.sheet == {}


def test_each_step_gets_fresh_geometry_objects_over_cached_buffers(studio):
    # Qt Quick 3D draws a geometry object only for the first Model that adopts it; reusing one across steps made every
    # carried-over part vanish during playback. The buffers are cached; the Qt objects are not.
    studio.setStep(3)
    first = {g.shapeId: g for g in studio.shapes}
    studio.setStep(4)
    second = {g.shapeId: g for g in studio.shapes}
    shared = set(first) & set(second)
    assert shared
    for sid in shared:
        assert first[sid] is not second[sid]
        assert first[sid]._vbytes is second[sid]._vbytes
