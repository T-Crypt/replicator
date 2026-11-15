"""Corpus export and verification. Export and verify share one row computation, so a row that was written can
always be re-checked by rebuilding the program it stores."""
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from replicator import FIXTURES
from replicator.core.evaluate import Evaluator
from replicator.core.program import check
from replicator.llm import client
import tools.corpus as corpus

FIX = FIXTURES
ROW_KEYS = {"id", "file", "prompt", "engine", "program", "geometry", "mass_kg", "mass_assumed", "verdict", "kernel"}


@pytest.fixture(scope="module")
def corpus_out(tmp_path_factory):
    out = tmp_path_factory.mktemp("corpus") / "corpus.jsonl"
    assert corpus.main(["export", str(FIX), "-o", str(out)]) == 0
    return out


def rows_of(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def test_export_writes_one_row_per_valid_fixture(corpus_out):
    rows = rows_of(corpus_out)
    names = sorted(p.name for p in FIX.glob("*.json"))
    assert sorted(Path(r["file"]).name for r in rows) == names   # every fixture is a valid program, none skipped
    assert all(set(r) == ROW_KEYS for r in rows)
    for key in ("parts", "volume", "size", "digest"):
        assert all(key in r["geometry"] for r in rows)


def test_rocket_engine_parts_match_an_independent_build(corpus_out):
    row = next(r for r in rows_of(corpus_out) if Path(r["file"]).name == "rocket_engine.json")
    shapes = Evaluator(FIX).step(check(json.loads((FIX / "rocket_engine.json").read_text())))
    assert row["geometry"]["parts"] == len(shapes)


def test_verify_rebuilds_every_row_of_a_fresh_export(corpus_out, capsys):
    rows = rows_of(corpus_out)
    assert corpus.main(["verify", str(corpus_out)]) == 0
    out = capsys.readouterr().out.splitlines()
    ok = [l for l in out if l.startswith("ok ")]
    assert len(ok) == len(rows)
    assert {l.split()[2] for l in ok} == {r["file"] for r in rows}
    assert out[-1] == f"{len(rows)}/{len(rows)} rows re-verify"


def test_verify_flags_a_tampered_program(corpus_out, tmp_path, capsys):
    row = next(r for r in rows_of(corpus_out) if Path(r["file"]).name == "rocket_engine.json")
    program = json.loads(json.dumps(row["program"]))
    op = next(o for o in program["ops"] if isinstance(o.get("params", {}).get("radius"), (int, float)))
    op["params"]["radius"] *= 2
    row["program"] = program          # geometry and id stay the stored ones: that is the drift
    bad = tmp_path / "tampered.jsonl"
    bad.write_text(json.dumps(row) + "\n")
    assert corpus.main(["verify", str(bad)]) == 1
    out = capsys.readouterr().out
    line = next(l for l in out.splitlines() if l.startswith("MISMATCH"))
    assert row["id"] in line and row["file"] in line
    assert "id" in line and "geometry" in line
    assert out.splitlines()[-1] == "0/1 rows re-verify"


def test_replicator_folder_yields_only_its_program(tmp_path):
    (tmp_path / "x.replicator" / "history").mkdir(parents=True)
    prog = (FIX / "quadcopter_drone.json").read_text()
    (tmp_path / "x.replicator" / "program.json").write_text(prog)
    (tmp_path / "x.replicator" / "history" / "0001.json").write_text(prog)   # a valid program, still excluded
    out = tmp_path / "rows.jsonl"
    assert corpus.main(["export", str(tmp_path), "-o", str(out)]) == 0
    rows = rows_of(out)
    assert [Path(r["file"]).name for r in rows] == ["program.json"]
    assert rows[0]["program"] == json.loads(prog)


def test_files_that_are_not_programs_are_skipped(tmp_path, capsys):
    good = tmp_path / "vector.json"
    good.write_text((FIX / "vector_engine.json").read_text())
    (tmp_path / "note.json").write_text('{"hello": "world"}')
    (tmp_path / "broken.json").write_text("not json")
    out = tmp_path / "rows.jsonl"
    assert corpus.main(["export", str(good), str(tmp_path / "note.json"), str(tmp_path / "broken.json"),
                       "-o", str(out)]) == 0
    rows = rows_of(out)
    assert [r["file"] for r in rows] == [str(good)]
    out_text = capsys.readouterr().out
    assert f"skip {tmp_path / 'note.json'}: version must be 1" in out_text
    assert f"skip {tmp_path / 'broken.json'}:" in out_text
    assert "1 programs, 2 skipped" in out_text


def test_stamp_source_records_and_preserves_origin():
    program = {"version": 1, "ops": [{"id": "a", "op": "box", "params": {"size": [1, 1, 1]}}]}
    out = client.stamp_source(program, "a small box", "local")
    assert out is program
    assert out["source"]["prompt"] == "a small box"
    assert out["source"]["engine"] == "local"
    assert out["source"]["date"] == datetime.now(timezone.utc).date().isoformat()
    check(out)    # validation tolerates the extra top-level key
    again = client.stamp_source(out, "something else", "coder")
    assert again["source"] == out["source"]   # an existing source is never overwritten
