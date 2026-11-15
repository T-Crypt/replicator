"""Benchmark v0. Task instances are pinned by seed, scores come out of the built solid, and the
runner and report behave exactly as specified. No model calls: the network is monkeypatched and
the dream step is stubbed where a trial is run end to end."""
import io
import json
from pathlib import Path

import pytest

import tools.bench
from bench.score import score
from bench.tasks import TASKS, flange, house, lamp
from replicator import FIXTURES
from replicator.llm import client

ROOT = Path(__file__).parent.parent
HOUSE = FIXTURES / "house_two_bed.json"
LAMP = ROOT / "tests" / "data" / "desk_lamp_flat.json"


def flange_program(p: dict, holes: int | None = None) -> dict:
    """The exact solid the flange prompt describes: a disc, the bore and the bolt holes cut out."""
    n = p["n"] if holes is None else holes
    return {
        "version": 1, "name": "Pipe flange", "units": "mm",
        "ops": [
            {"id": "disc", "op": "cylinder", "label": "Flange body", "part": "flange",
             "params": {"radius": p["od"] / 2, "height": p["t"]}},
            {"id": "bore_cut", "op": "cylinder", "label": "Bore", "part": "flange",
             "params": {"radius": p["bore"] / 2, "height": p["t"] + 4}},
            {"id": "bolt", "op": "cylinder", "label": "Bolt hole", "part": "flange",
             "params": {"radius": p["h"] / 2, "height": p["t"] + 4,
                        "translate": [p["pcd"] / 2, 0, 0]}},
            {"id": "bolts", "op": "array", "label": "Bolt hole circle", "part": "flange",
             "input": "bolt", "params": {"mode": "radial", "count": n, "angle": 360, "axis": "y"}},
            {"id": "flange", "op": "boolean", "label": "Flange", "part": "flange",
             "inputs": ["disc", "bore_cut", "bolts"], "params": {"mode": "difference"}},
        ],
    }


@pytest.mark.parametrize("name", sorted(TASKS))
def test_same_seed_gives_the_same_instance(name):
    m = TASKS[name]
    assert m.instance(7) == m.instance(7)


def test_different_seeds_give_different_flange_prompts():
    assert flange.instance(13).prompt != flange.instance(14).prompt


def test_exact_flange_scores_full_marks():
    inst = flange.instance(13)
    result = score(flange_program(inst.params), inst)
    assert result["gate"] is True
    assert result["blocking"] == 0
    assert all(a["passed"] for a in result["assertions"])
    assert result["score"] == 1.0


def test_flange_missing_a_bolt_hole_fails_genus():
    inst = flange.instance(13)
    result = score(flange_program(inst.params, holes=inst.params["n"] - 1), inst)
    genus = next(a for a in result["assertions"] if a["kind"] == "genus")
    assert genus["passed"] is False
    assert result["score"] < 1.0
    assert result["score"] == 0.825


def test_invalid_program_scores_zero_at_the_gate():
    result = score({"version": 1, "ops": [{"id": "x", "op": "warpdrive"}]}, flange.instance(13))
    assert result["score"] == 0.0
    assert result["gate"] is False
    assert result["assertions"] == []
    assert "unknown op" in result["reason"]


def test_build_that_cannot_finish_scores_zero():
    prog = {"version": 1, "ops": [
        {"id": "a", "op": "box", "params": {"size": [10, 10, 10], "translate": [0, 0, 0]}},
        {"id": "b", "op": "box", "params": {"size": [10, 10, 10], "translate": [100, 0, 0]}},
        {"id": "both", "op": "boolean", "inputs": ["a", "b"], "params": {"mode": "intersection"}},
    ]}
    result = score(prog, flange.instance(13))
    assert result["gate"] is False
    assert result["score"] == 0.0
    assert "build failed" in result["reason"]


def test_house_fixture_scores_full_marks_at_a_matching_area():
    seed = next(s for s in range(200) if house.instance(s).params["A"] in (60, 70))
    inst = house.instance(seed)
    program = json.loads(HOUSE.read_text())
    result = score(program, inst, HOUSE.parent)
    # Measured 2026-11-14: the re-roofed fixture passes every assertion when A is 60 or 70
    # (its walls enclose about 88 m^2), top_of included.
    assert inst.params["A"] in (60, 70)
    assert result["blocking"] == 0
    assert all(a["passed"] for a in result["assertions"])
    assert result["score"] == 1.0


def test_flat_lamp_fails_the_proportion_and_alignment_assertion():
    inst = lamp.instance(14)
    assert inst.params["H"] == 400
    program = json.loads(LAMP.read_text())
    result = score(program, inst, LAMP.parent)
    row = next(a for a in result["assertions"] if a["label"] == "proportion and alignment")
    assert row["passed"] is False
    assert "proportion" in row["observed"]
    assert "alignment" in row["observed"]
    assert result["blocking"] == 5
    assert result["score"] == 0.4


def test_chat_sends_the_seed_when_set(monkeypatch):
    seen = {}

    def fake_urlopen(req, timeout=None):
        seen["body"] = json.loads(req.data.decode())
        return io.BytesIO(b'{"choices": [{"message": {"content": "ok"}}]}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    client.SEED.set(7)
    try:
        client.chat([{"role": "user", "content": "x"}], "local")
    finally:
        client.SEED.set(None)
    assert seen["body"]["seed"] == 7
    client.chat([{"role": "user", "content": "x"}], "local")
    assert "seed" not in seen["body"]


def test_run_saves_programs_and_logs_one_row_per_trial(monkeypatch, tmp_path):
    monkeypatch.setattr(client, "dream", lambda prompt, engine: flange_program(flange.instance(13).params))
    rc = tools.bench.run("local", "flange", 13, 2, tmp_path)
    assert rc == 0
    saved = tmp_path / "local" / "flange" / "seed13" / "program.json"
    assert saved.is_file()
    rows = [json.loads(l) for l in (tmp_path / "local" / "results.jsonl").read_text().splitlines()]
    assert [r["seed"] for r in rows] == [13, 14]
    assert rows[0]["gate"] is True
    assert rows[0]["score"] == 1.0
    assert rows[0]["model"] == "local"
    assert rows[1]["gate"] is True and rows[1]["score"] < 1.0
    keys = {"task", "task_hash", "class", "category", "seed", "engine", "model",
            "commit", "prompt", "score", "gate", "blocking", "assertions", "seconds"}
    assert keys <= set(rows[0])
    assert rows[0]["class"] == "spec" and rows[0]["category"] == "machine"


def test_run_scores_zero_when_dream_fails(monkeypatch, tmp_path):
    def broken(prompt, engine):
        raise ValueError("endpoint refused the connection")

    monkeypatch.setattr(client, "dream", broken)
    rc = tools.bench.run("local", "flange", 13, 1, tmp_path)
    assert rc == 0
    rows = [json.loads(l) for l in (tmp_path / "local" / "results.jsonl").read_text().splitlines()]
    assert rows[0]["score"] == 0.0
    assert rows[0]["gate"] is False
    assert "refused the connection" in rows[0]["reason"]


def test_report_prints_tables_with_the_expected_mean(tmp_path):
    eng = tmp_path / "fake"
    eng.mkdir()
    rows = [
        {"task": "flange", "seed": 13, "engine": "fake", "model": "fake-model",
         "score": 1.0, "gate": True, "blocking": 0, "assertions": []},
        {"task": "flange", "seed": 14, "engine": "fake", "model": "fake-model",
         "score": 0.5, "gate": False, "blocking": 2, "assertions": []},
    ]
    (eng / "results.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    text = tools.bench.report(tmp_path)
    assert "## flange" in text
    assert "seed 13" in text and "seed 14" in text
    assert "fake (fake-model)" in text
    assert "0.750" in text       # mean of 1.0 and 0.5, per-task and overall
    assert "1/2" in text          # gate pass rate


def test_report_on_an_empty_outdir_says_so(tmp_path):
    assert "no results" in tools.bench.report(tmp_path)
