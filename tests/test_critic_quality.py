import time

import pytest

from replicator import knowledge
from replicator.core import assembly, critique, materials, physics
from replicator.core.evaluate import Evaluator


def prog(*ops):
    return {"version": 1, "units": "mm", "ops": list(ops)}


def box(oid, size, at=(0, 0, 0), **kw):
    return {"id": oid, "op": "box", "component": oid, "params": {"size": size, "translate": list(at)}, **kw}


def built(p):
    shapes = Evaluator().step(p)
    return shapes, assembly.components(p, shapes)


def kinds(p):
    return [(i.kind, i.subject) for i in critique.critique(p, *built(p))]


def test_a_duct_that_plugs_into_a_port_is_contact_not_clipping():
    port = box("port", [100, 100, 100])
    duct = {"id": "duct", "op": "cylinder", "component": "duct", "label": "Fuel inlet duct",
            "params": {"radius": 20, "height": 120, "translate": [0, 50, 0]}}
    cover = dict(duct, id="cover", component="cover", label="Cover plate")
    assert kinds(prog(port, duct)) == []
    assert kinds(prog(port, cover)) == [("clipping", "cover")]


def test_a_part_hanging_loose_in_a_hollow_body_floats():
    shell = {"id": "shell", "op": "tube", "component": "shell", "params": {"height": 200, "radius": 100, "wall": 10}}
    loose = {"id": "ball", "op": "sphere", "component": "ball", "params": {"radius": 20}}
    held = {"id": "ball", "op": "sphere", "component": "ball", "params": {"radius": 20, "translate": [75, 0, 0]}}
    assert kinds(prog(shell, loose)) == [("floating", "ball")]
    assert kinds(prog(shell, held)) == []


def test_array_copies_that_stack_or_overlap_are_reported():
    def arr(x, mode="radial", count=4):
        return prog(box("src", [20, 20, 20], (x, 0, 0)), {"id": "ring", "op": "array", "input": "src",
                    "component": "ring", "params": {"mode": mode, "count": count, "axis": "y"}})
    assert kinds(arr(0)) == [("array_overlap", "ring")]
    assert kinds(arr(100)) == []
    msg = critique.critique(*[arr(0)] + list(built(arr(0))))[0].message
    assert msg.startswith("The 4 copies in ring overlap each other (75% of their volume is shared)")


def test_a_sliver_wall_is_a_warning():
    p = prog({"id": "t", "op": "tube", "component": "t", "label": "Casing",
              "params": {"height": 400, "radius": 100, "wall": 0.05}})
    assert kinds(p) == [("thin_wall", "t")]
    p["ops"][0]["params"]["wall"] = 3
    assert kinds(p) == []


def test_missing_needs_the_head_noun_and_tolerates_plurals():
    p = prog(box("a", 10, label="Fuel tank"), box("b", 10, (10, 0, 0), label="Return valve"))
    p["blueprint"] = {"parts": [{"name": "Fuel pump"}, {"name": "Main propellant valves"}, {"name": "Fuel tank"}]}
    assert [i.message for i in critique.critique(p, *built(p)) if i.kind == "missing"] == [
        "The blueprint lists Fuel pump, but no part is named for it."]


def test_overlap_check_on_a_400_op_grid_is_fast():
    n = 20
    p = prog(*[box(f"b{i}_{j}", 12, (i * 10, 0, j * 10)) for i in range(n) for j in range(n)])
    shapes, comps = built(p)
    b = critique.Build(p, shapes, comps)
    best = min(_time(lambda: critique.overlaps(b)) for _ in range(3))
    assert critique.overlaps(b) == []
    assert best < 0.150, f"{best * 1000:.0f} ms"
    assert _time(lambda: critique.critique(p, shapes, comps)) < 0.300


def _time(fn):
    t = time.perf_counter()
    fn()
    return time.perf_counter() - t


def test_principal_inertia_of_a_steel_box_matches_the_analytic_values():
    p = {"version": 1, "units": "mm", "materials": {"steel": {}}, "ops": [
        {"id": "b", "op": "box", "material": "steel", "params": {"size": [100, 200, 300], "translate": [500, 70, -40]}}]}
    m = physics.properties(p, Evaluator().step(p))
    mass = 0.1 * 0.2 * 0.3 * 7850
    expect = sorted(mass / 12 * (a * a + c * c) for a, c in ((0.2, 0.3), (0.1, 0.3), (0.1, 0.2)))
    assert m.kg == pytest.approx(47.1)
    assert m.inertia == pytest.approx(expect, rel=1e-6)
    assert all(type(v) is float for v in m.inertia)
    assert [round(v, 4) for v in m.inertia] == [0.1963, 0.3925, 0.5103]


def _table(legs_at, top_at=(0, 0, 0), top=(400, 20, 400)):
    ops = [box("top", list(top), (top_at[0], 410 + top_at[1], top_at[2]), material="steel")]
    ops += [box(f"leg{k}", [30, 400, 30], (x, 200, z), material="steel") for k, (x, z) in enumerate(legs_at)]
    return {"version": 1, "units": "mm", "materials": {"steel": {}}, "ops": ops}


def test_a_four_legged_table_stands_and_overhanging_mass_tips_it():
    legs = [(-170, -170), (170, -170), (-170, 170), (170, 170)]
    m = physics.properties(_table(legs), Evaluator().step(_table(legs)))
    assert (m.stands, m.cg[0], m.cg[2]) == (True, 0.0, 0.0)
    off = _table(legs, top_at=(300, 0, 0), top=(900, 20, 400))
    assert physics.properties(off, Evaluator().step(off)).stands is False
    three = _table(legs[:3])
    assert physics.properties(three, Evaluator().step(three)).stands is True


def test_material_presets_are_physically_plausible():
    bare = {"Metal", "Aerospace"}
    for key, (_, group, d) in materials.PRESETS.items():
        if d["metalness"] >= 0.99:
            assert group in bare and not key.startswith(("carbon", "peek", "kevlar", "tps", "steel_cerakote")), key
        else:
            assert d["metalness"] <= 0.2 or key == "cast_iron", key
        if d["metalness"] < 0.5:
            assert sum(d["base_color"]) / 3 <= 0.9, key
    assert materials.PRESETS["carbon_fibre"][2]["metalness"] == 0.1
    assert materials.PRESETS["cast_iron"][2]["metalness"] == 1.0


def test_new_knowledge_cards_are_picked_and_short():
    pick = lambda q: [c.name for c in knowledge.pick(q)]  # noqa: E731
    assert pick("a powered exoskeleton for lifting") == ["exoskeleton"]
    assert pick("a quadcopter drone with 5 inch props") == ["multirotor_drone"]
    assert pick("a car wheel with a brake disc and strut") == ["car_wheel_corner"]
    for name in ("exoskeleton", "multirotor_drone", "car_wheel_corner"):
        card = next(c for c in knowledge.CARDS if c.name == name)
        assert len(card.body) < 3400 and card.keywords
