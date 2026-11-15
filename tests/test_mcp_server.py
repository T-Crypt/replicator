"""The MCP tools never leave a broken program on disk."""
import json

import pytest

pytest.importorskip("mcp")
from replicator import mcp_server as M  # noqa: E402

PROG = {"version": 1, "name": "Bracket", "units": "mm", "materials": {},
        "ops": [{"id": "plate", "op": "box", "params": {"size": [60, 6, 40], "center": True}},
                {"id": "hole", "op": "cylinder", "params": {"radius": 4, "height": 20, "center": True}},
                {"id": "body", "op": "boolean", "inputs": ["plate", "hole"], "params": {"mode": "difference"}}]}


def test_write_patch_and_reject(tmp_path):
    p = str(tmp_path / "b.json")
    assert M.write_program(p, PROG)["ok"]
    good = M.patch_program(p, [{"op": "replace", "path": "/ops/1/params/radius", "value": 6}])
    assert good["ok"] and good["report"]["parts"] == 1 and good["report"]["blocking"] == 0
    before = (tmp_path / "b.json").read_text()
    bad = M.patch_program(p, [{"op": "replace", "path": "/ops/2/inputs", "value": ["plate", "nope"]}])
    assert not bad["ok"] and "nope" in bad["error"]
    assert (tmp_path / "b.json").read_text() == before
    assert json.loads((tmp_path / "b.prev.json").read_text())["ops"][1]["params"]["radius"] == 4


def test_invalid_program_is_never_written(tmp_path):
    p = tmp_path / "x.json"
    r = M.write_program(str(p), dict(PROG, ops=[{"id": "a", "op": "box", "size": [1, 1, 1]}]))
    assert not r["ok"] and not p.exists()


def test_report_step_and_export_step(tmp_path):
    p = str(tmp_path / "b.json")
    M.write_program(p, PROG)
    assert M.build_report(p, step=0)["report"]["ops"] == 1
    out = M.export(p, str(tmp_path / "b.step"))
    assert out["ok"] and (tmp_path / "b.step").read_text().startswith("ISO-10303-21;")
