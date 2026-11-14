"""Offline tests for what comes back from a model: JSON extraction, lossless tidy-up, repair messages."""
import copy

import pytest

from replicator.llm import client

DOME_CW = [[0, 130], [140, 110], [220, 75], [260, 25], [260, 0], [0, 0]]


def prog(*ops):
    return {"version": 1, "name": "t", "units": "mm", "materials": {}, "ops": list(ops)}


def test_extract_takes_last_fence_and_survives_comments_and_trailing_commas():
    reply = ('<think>```json\n{"x": 1}\n```</think>Here:\n```json\n{\n "a": [1, 2,], // note\n'
             ' "b": "http://x.y/z", }\n```\nDone.')
    assert client.extract_json(reply) == {"a": [1, 2], "b": "http://x.y/z"}


def test_extract_empty_reply_says_why():
    with pytest.raises(ValueError, match="empty"):
        client.extract_json("<think>long</think>  ")


def test_clockwise_revolve_is_reversed_and_builds():
    p = prog({"id": "dome", "op": "revolve", "params": {"points": DOME_CW, "translate": [0, 300, 0]}})
    assert client.problems(copy.deepcopy(p)) != []
    client.tidy(p)
    assert p["ops"][0]["params"]["points"] == DOME_CW[::-1]
    assert client.problems(p) == []


def test_counter_clockwise_profile_is_left_alone():
    pts = DOME_CW[::-1]
    p = prog({"id": "dome", "op": "revolve", "params": {"points": pts}})
    client.tidy(p)
    assert p["ops"][0]["params"]["points"] == pts


def test_null_params_are_dropped_not_guessed():
    p = prog({"id": "b", "op": "box", "input": None, "params": {"size": [1, 2, 3], "center": None}})
    client.tidy(p)
    assert p["ops"][0]["params"] == {"size": [1, 2, 3]}
    assert client.problems(p) == []


def test_center_true_is_dropped_only_where_the_op_has_no_center():
    p = prog({"id": "r", "op": "sphere", "params": {"radius": 2, "center": True}},
             {"id": "k", "op": "box", "params": {"size": [1, 1, 1], "center": True}},
             {"id": "f", "op": "cylinder", "params": {"height": 5, "radius": 2, "center": False}})
    client.tidy(p)
    assert "center" not in p["ops"][0]["params"] and p["ops"][1]["params"]["center"] is True
    assert p["ops"][2]["params"]["center"] is False
    assert client.problems(p) == []


def test_rotate_op_is_a_transform_but_only_when_it_is_purely_placement():
    p = prog({"id": "a", "op": "box", "params": {"size": [1, 1, 1]}},
             {"id": "r", "op": "rotate", "input": "a", "rotate": [0, 90, 0]},
             {"id": "q", "op": "rotate", "input": "a", "params": {"angle": 90}})
    client.tidy(p)
    assert p["ops"][1]["op"] == "transform" and p["ops"][2]["op"] == "rotate"
    assert client.problems(prog(p["ops"][0], p["ops"][1])) == []


def test_tidy_ignores_malformed_programs():
    assert client.tidy([1]) == [1]
    p = {"ops": [None, {"op": "revolve", "params": {"points": "abc"}}, {"op": "box", "params": []}]}
    assert client.tidy(p) is p


def test_repair_message_lists_errors_and_adds_hint_for_empty_results():
    msg = client.repair_message(["op a (revolve): result is empty (a difference removed everything)", "x"])
    assert "- op a (revolve)" in msg and "- x" in msg and "wound clockwise" in msg
    assert "Hints" not in client.repair_message(["ops[0]: unknown op 'cone'"])


def test_op_reference_hides_import_only_ops():
    ref = client.op_reference()
    assert "- mesh:" not in ref and "- revolve:" in ref


def test_ops_written_before_their_inputs_are_reordered():
    from replicator.llm.client import tidy
    p = {"version": 1, "units": "mm", "ops": [
        {"id": "u", "op": "boolean", "inputs": ["a", "b"], "params": {"mode": "union"}},
        {"id": "a", "op": "box", "params": {"size": 10}},
        {"id": "b", "op": "sphere", "params": {"radius": 6}}]}
    assert [o["id"] for o in tidy(p)["ops"]] == ["a", "b", "u"]


def test_a_cycle_is_left_for_validation():
    from replicator.llm.client import tidy
    p = {"version": 1, "units": "mm", "ops": [
        {"id": "a", "op": "transform", "input": "b"}, {"id": "b", "op": "transform", "input": "a"}]}
    assert [o["id"] for o in tidy(p)["ops"]] == ["a", "b"]
