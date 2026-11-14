import json
import math
from pathlib import Path

import pytest

from replicator import knowledge
from replicator.core import assembly, critique
from replicator.core.evaluate import EvalError, Evaluator
from replicator.core.ops_engineering import nozzle_contour
from replicator.core.program import ProgramError, delete_component, duplicate_component
from replicator.llm.client import _outside_scope

FIX = Path(__file__).parent.parent / "fixtures"


def prog(*ops):
    return {"version": 1, "units": "mm", "ops": list(ops)}


def build(p):
    shapes = Evaluator().step(p)
    return shapes, assembly.components(p, shapes)


def issues(p):
    return [(i.kind, i.subject) for i in critique.critique(p, *build(p))]


def extent(s):
    b = s.manifold.bounding_box()
    return [round(b[i + 3] - b[i], 1) for i in range(3)]


def test_tube_is_hollow_with_the_wall_asked_for():
    (s,) = Evaluator().step(prog({"id": "t", "op": "tube", "params": {"height": 100, "radius": 40, "wall": 4,
                                                                       "segments": 256}}))
    assert extent(s) == [80.0, 100.0, 80.0]
    assert s.manifold.volume() == pytest.approx(math.pi * (40 ** 2 - 36 ** 2) * 100, rel=0.01)


def test_nozzle_exit_follows_the_expansion_ratio():
    inner = nozzle_contour(rt=10, eps=25, cr=4, lc=None, frac=0.8)
    assert inner[:, 1].min() == pytest.approx(10, abs=0.01)
    assert inner[-1, 1] == pytest.approx(50, abs=0.01)
    assert inner[0, 1] == pytest.approx(20, abs=0.01)
    (s,) = Evaluator().step(prog({"id": "n", "op": "nozzle", "params": {"throat_radius": 10, "expansion_ratio": 25,
                                                                         "wall": 1}}))
    assert extent(s)[0] == pytest.approx(102, abs=0.5)


def test_rotor_and_grille_build_solids():
    shapes = Evaluator().step(prog(
        {"id": "r", "op": "rotor", "params": {"hub_radius": 20, "tip_radius": 60, "chord": 20, "blades": 8}},
        {"id": "g", "op": "grille", "params": {"size": [100, 2, 100], "hole_size": 6}, "translate": [200, 0, 0]}))
    assert [s.manifold.status().name for s in shapes] == ["NoError", "NoError"]
    assert extent(shapes[0])[0] == pytest.approx(120, abs=1)
    assert shapes[1].manifold.volume() < 100 * 2 * 100 * 0.8


def test_engineering_ops_reject_impossible_params():
    with pytest.raises(EvalError, match="wall must be thinner"):
        Evaluator().step(prog({"id": "t", "op": "tube", "params": {"height": 10, "radius": 5, "wall": 6}}))
    with pytest.raises(EvalError, match="tip_radius"):
        Evaluator().step(prog({"id": "r", "op": "rotor", "params": {"hub_radius": 50, "tip_radius": 40, "chord": 9}}))


def test_critic_finds_a_ring_on_the_wrong_axis_and_accepts_the_fixed_one():
    body = {"id": "body", "op": "tube", "component": "body",
            "params": {"height": 400, "radius": 100, "wall": 5, "rotate": [90, 0, 0]}}
    ring = {"id": "ring", "op": "torus", "component": "ring",
            "params": {"major_radius": 87, "minor_radius": 8, "translate": [0, 0, 150]}}
    assert ("off_axis", "ring") in issues(prog(body, ring))
    ring["params"]["rotate"] = [90, 0, 0]
    assert issues(prog(body, ring)) == []


def test_critic_finds_floating_and_buried_parts():
    base = {"id": "base", "op": "box", "component": "base", "params": {"size": [100, 100, 100]}}
    far = {"id": "far", "op": "sphere", "component": "far", "params": {"radius": 10, "translate": [0, 300, 0]}}
    inside = {"id": "inside", "op": "sphere", "component": "inside", "params": {"radius": 10}}
    assert issues(prog(base, far)) == [("floating", "base"), ("floating", "far")]
    assert issues(prog(base, inside)) == [("buried", "inside")]


def test_critic_compares_with_the_blueprint():
    p = prog({"id": "a", "op": "box", "component": "frame", "label": "Frame", "params": {"size": [100, 100, 100]}})
    p["blueprint"] = {"dimensions": [100, 100, 300], "parts": [{"name": "Frame"}, {"name": "Turbopump"}]}
    assert issues(p) == [("size", ""), ("missing", "")]


def test_shipped_engine_has_no_blocking_issues():
    p = json.loads((FIX / "dirk_engine_v2.json").read_text())
    assert critique.blocking(critique.critique(p, *build(p))) == []


def test_delete_component_refuses_when_something_still_uses_it():
    p = prog({"id": "a", "op": "box", "component": "a", "params": {"size": 10}},
             {"id": "b", "op": "array", "input": "a", "component": "b", "params": {"mode": "linear", "count": 2}},
             {"id": "c", "op": "sphere", "component": "c", "params": {"radius": 5}})
    with pytest.raises(ProgramError, match="b still use"):
        delete_component(p, "a")
    assert [o["id"] for o in delete_component(p, "c")["ops"]] == ["a", "b"]


def test_duplicate_component_renames_the_chain_and_moves_only_the_result():
    p = prog({"id": "a", "op": "box", "component": "pod", "params": {"size": 10}},
             {"id": "b", "op": "round", "input": "a", "params": {"radius": 1}})
    out, new = duplicate_component(p, "pod", [50, 0, 0])
    assert new == "pod_2"
    a2, b2 = out["ops"][2:]
    assert (a2["id"], b2["id"], b2["input"]) == ("a_2", "b_2", "a_2")
    assert "translate" not in a2["params"] and b2["params"]["translate"] == [50, 0, 0]


def test_scoped_edit_rejects_changes_outside_the_part():
    old = prog({"id": "a", "op": "box", "params": {"size": 10}}, {"id": "b", "op": "box", "params": {"size": 5}})
    new = json.loads(json.dumps(old))
    new["ops"][1]["params"]["size"] = 9
    assert _outside_scope(old, new, {"a"}) == ["op b is outside the part being reworked and must stay exactly as it was"]
    assert _outside_scope(old, new, {"b"}) == []


def test_knowledge_cards_are_picked_by_subject():
    assert [c.name for c in knowledge.pick("a rocket engine with turbopumps")] == ["rocket_engine"]
    assert [c.name for c in knowledge.pick("a gaming PC with a big graphics card")] == ["desktop_pc"]
    assert knowledge.pick("a ceramic teapot") == []


def test_mass_is_volume_times_density_in_plain_floats():
    from replicator.core import physics
    p = {"version": 1, "units": "mm", "materials": {"steel": {}}, "ops": [
        {"id": "c", "op": "box", "material": "steel", "params": {"size": 100, "translate": [0, 50, 0]}}]}
    m = physics.properties(p, Evaluator().step(p))
    assert (m.kg, m.cg, m.stands) == (7.85, [0.0, 50.0, 0.0], True)
    assert type(m.kg) is float and all(type(v) is float for v in m.by_component.values())


def test_a_top_heavy_object_tips():
    p = prog({"id": "post", "op": "box", "component": "post", "params": {"size": [10, 200, 10], "translate": [0, 100, 0]}},
             {"id": "arm", "op": "box", "component": "arm", "params": {"size": [300, 20, 20], "translate": [150, 210, 0]}})
    assert ("tips", "") in issues(p)


def test_null_inputs_from_a_model_are_ignored():
    from replicator.core.program import validate
    assert validate(prog({"id": "a", "op": "box", "input": None, "inputs": [], "params": {"size": 10}})) == []
