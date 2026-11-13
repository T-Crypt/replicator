from __future__ import annotations

import math
from pathlib import Path

import pytest

from replicator.core.export import export
from replicator.core.evaluate import EvalError, Evaluator
from replicator.core.program import Project, ProgramError, apply_patch, validate


def _program(ops, materials=None):
    return {
        "version": 1,
        "name": "test",
        "units": "mm",
        "materials": materials or {},
        "ops": ops,
    }


def _box(i, size, translate=None):
    op = {"id": i, "op": "box", "params": {"size": size}}
    if translate is not None:
        op["translate"] = translate
    return op


def _assert_shape(m, expected_volume):
    assert not m.is_empty()
    assert m.volume() > 0
    assert m.volume() == pytest.approx(expected_volume, rel=0.02)


def test_primitives_volumes_and_y_up_cylinder():
    ev = Evaluator()

    box = ev.run(_program([
        {"id": "box", "op": "box", "params": {"size": [2.0, 3.0, 4.0]}}
    ]))[0]["box"]
    _assert_shape(box, 24.0)

    cyl = ev.run(_program([
        {"id": "cyl", "op": "cylinder", "params": {"height": 10.0, "radius": 2.0, "segments": 256}}
    ]))[0]["cyl"]
    _assert_shape(cyl, math.pi * 2.0**2 * 10.0)
    lo, hi = cyl.bounding_box()[:3], cyl.bounding_box()[3:]
    assert hi[1] - lo[1] == pytest.approx(10.0, rel=0.02)
    assert (lo[1] + hi[1]) / 2.0 == pytest.approx(0.0, abs=1e-3)

    sph = ev.run(_program([
        {"id": "sph", "op": "sphere", "params": {"radius": 2.0, "segments": 256}}
    ]))[0]["sph"]
    _assert_shape(sph, 4.0 / 3.0 * math.pi * 2.0**3)

    tor = ev.run(_program([
        {"id": "tor", "op": "torus", "params": {"major_radius": 2.0, "minor_radius": 0.5, "segments": 256}}
    ]))[0]["tor"]
    _assert_shape(tor, 2.0 * math.pi**2 * 2.0 * 0.5**2)

    cap = ev.run(_program([
        {"id": "cap", "op": "capsule", "params": {"height": 4.0, "radius": 1.0, "segments": 256}}
    ]))[0]["cap"]
    _assert_shape(cap, math.pi * 1.0**2 * 4.0 + 4.0 / 3.0 * math.pi * 1.0**3)

    ext = ev.run(_program([
        {"id": "ext", "op": "extrude", "params": {"points": [[0.0, 0.0], [4.0, 0.0], [0.0, 3.0]], "height": 5.0}}
    ]))[0]["ext"]
    _assert_shape(ext, 6.0 * 5.0)

    rev = ev.run(_program([
        {"id": "rev", "op": "revolve", "params": {
            "points": [[0.0, 0.0], [2.0, 0.0], [2.0, 4.0], [0.0, 4.0]],
            "segments": 256,
        }}
    ]))[0]["rev"]
    _assert_shape(rev, 16.0 * math.pi)


def test_boolean_box_volumes():
    ev = Evaluator()

    union_prog = _program([
        _box("a", [4.0, 4.0, 4.0]),
        _box("b", [4.0, 4.0, 4.0], [2.0, 0.0, 0.0]),
        {"id": "union", "op": "boolean", "params": {"mode": "union"}, "inputs": ["a", "b"]},
    ])
    diff_prog = _program([
        _box("a", [4.0, 4.0, 4.0]),
        _box("b", [4.0, 4.0, 4.0], [2.0, 0.0, 0.0]),
        {"id": "diff", "op": "boolean", "params": {"mode": "difference"}, "inputs": ["a", "b"]},
    ])
    inter_prog = _program([
        _box("a", [4.0, 4.0, 4.0]),
        _box("b", [4.0, 4.0, 4.0], [2.0, 0.0, 0.0]),
        {"id": "inter", "op": "boolean", "params": {"mode": "intersection"}, "inputs": ["a", "b"]},
    ])

    _assert_shape(ev.run(union_prog)[0]["union"], 96.0)
    _assert_shape(ev.run(diff_prog)[0]["diff"], 32.0)
    _assert_shape(ev.run(inter_prog)[0]["inter"], 32.0)


def test_arrays():
    ev = Evaluator()

    linear_prog = _program([
        _box("base", [1.0, 1.0, 1.0]),
        {"id": "lin", "op": "array", "params": {"mode": "linear", "count": 3, "offset": [2.0, 0.0, 0.0]}, "input": "base"},
    ])
    _assert_shape(ev.run(linear_prog)[0]["lin"], 3.0)

    radial_prog = _program([
        _box("base", [1.0, 1.0, 1.0], [4.0, 0.0, 0.0]),
        {"id": "rad", "op": "array", "params": {"mode": "radial", "count": 4, "axis": "y"}, "input": "base"},
    ])
    _assert_shape(ev.run(radial_prog)[0]["rad"], 4.0)

    mirror_prog = _program([
        _box("base", [1.0, 1.0, 1.0], [1.0, 0.0, 0.0]),
        {"id": "mir", "op": "array", "params": {"mode": "mirror", "count": 2, "plane": [1.0, 0.0, 0.0]}, "input": "base"},
    ])
    _assert_shape(ev.run(mirror_prog)[0]["mir"], 2.0)


@pytest.mark.parametrize(
    "program,needle",
    [
        (
            _program([{"id": "a", "op": "wobble", "params": {}}]),
            "unknown op",
        ),
        (
            _program([
                _box("a", [1.0, 1.0, 1.0]),
                _box("a", [1.0, 1.0, 1.0], [2.0, 0.0, 0.0]),
            ]),
            "duplicate id",
        ),
        (
            _program([
                {"id": "a", "op": "transform", "params": {}, "input": "b"},
                _box("b", [1.0, 1.0, 1.0]),
            ]),
            "not an earlier op id",
        ),
        (
            _program([{"id": "a", "op": "box", "params": {}}]),
            "needs params",
        ),
        (
            _program([{"id": "a", "op": "box", "params": {"size": [1.0, 1.0, 1.0], "bogus": 1}}]),
            "does not take params",
        ),
        (
            _program([_box("a", [1.0, 1.0, 1.0])], {"steel": {"base_color": [1, 1, 1]}}),
            "not defined in materials",
        ),
        (
            _program([
                _box("a", [1.0, 1.0, 1.0]),
                _box("b", [1.0, 1.0, 1.0]),
                {"id": "c", "op": "smooth", "params": {}, "inputs": ["a", "b"]},
            ]),
            "takes exactly one input",
        ),
    ],
)
def test_validate_reports_errors(program, needle):
    if needle == "not defined in materials":
        program["ops"][0]["material"] = "chrome"

    errors = validate(program)
    assert errors, f"expected a validation error mentioning {needle!r}"
    assert any(needle in e for e in errors)


def test_evaluator_cache_hits_and_single_invalidated_op():
    ev = Evaluator()
    prog = _program([
        _box("a", [4.0, 4.0, 4.0]),
        _box("b", [4.0, 4.0, 4.0], [2.0, 0.0, 0.0]),
        {"id": "c", "op": "boolean", "params": {"mode": "union"}, "inputs": ["a", "b"]},
    ])

    assert ev.run(prog)[0]
    assert ev.last_misses == 3

    assert ev.run(prog)[0]
    assert ev.last_hits == 3
    assert ev.last_misses == 0

    prog2 = _program([
        _box("a", [4.0, 4.0, 4.0]),
        _box("b", [4.0, 4.0, 4.0], [2.0, 0.0, 0.0]),
        {"id": "c", "op": "boolean", "params": {"mode": "intersection"}, "inputs": ["a", "b"]},
    ])
    assert ev.run(prog2)[0]
    assert ev.last_hits == 2
    assert ev.last_misses == 1


def test_step_hides_consumed_ops():
    ev = Evaluator()
    prog = _program([
        _box("a", [4.0, 4.0, 4.0]),
        _box("b", [4.0, 4.0, 4.0], [2.0, 0.0, 0.0]),
        {"id": "c", "op": "boolean", "params": {"mode": "union"}, "inputs": ["a", "b"]},
    ])

    assert [s.id for s in ev.step(prog, 0)] == ["a"]
    assert [s.id for s in ev.step(prog, 2)] == ["c"]


def test_apply_patch_replaces_without_mutating_and_invalid_patch_raises():
    prog = _program([
        {"id": "a", "op": "cylinder", "params": {"height": 10.0, "radius": 2.0}}
    ])

    patched = apply_patch(prog, [{"op": "replace", "path": "/ops/0/params/height", "value": 20.0}])

    assert patched["ops"][0]["params"]["height"] == 20.0
    assert prog["ops"][0]["params"]["height"] == 10.0
    assert validate(patched) == []

    with pytest.raises(ProgramError):
        apply_patch(prog, [{"op": "replace", "path": "/ops/0/op", "value": "nope"}])


def test_project_save_load_round_trip_and_history_numbering(tmp_path):
    prog = _program([
        _box("a", [1.0, 1.0, 1.0]),
        _box("b", [1.0, 1.0, 1.0], [2.0, 0.0, 0.0]),
    ])

    project = Project(tmp_path / "proj.replicator")
    n1 = project.save(prog, note="first")
    n2 = project.save(prog, note="second")

    assert n1 == 1
    assert n2 == 2
    assert (tmp_path / "proj.replicator" / "history" / "0001.json").exists()
    assert (tmp_path / "proj.replicator" / "history" / "0002.json").exists()

    loaded = project.load()
    assert loaded == prog
    assert project.version(1)["ops"][0]["id"] == "a"
    assert project.version(2)["ops"][1]["id"] == "b"


def test_export_glb_and_stl_and_empty_difference_eval_error(tmp_path):
    ev = Evaluator()
    prog = _program([
        _box("a", [4.0, 4.0, 4.0]),
        _box("b", [4.0, 4.0, 4.0], [2.0, 0.0, 0.0]),
        {"id": "c", "op": "boolean", "params": {"mode": "union"}, "inputs": ["a", "b"]},
    ])
    shapes = ev.step(prog)

    glb_path = tmp_path / "build.glb"
    stl_path = tmp_path / "build.stl"
    export(shapes, prog["materials"], glb_path)
    export(shapes, prog["materials"], stl_path)

    assert glb_path.stat().st_size > 0
    assert stl_path.stat().st_size > 0

    empty_diff_prog = _program([
        _box("a", [4.0, 4.0, 4.0]),
        _box("b", [10.0, 10.0, 10.0], [0.0, 0.0, 0.0]),
        {"id": "c", "op": "boolean", "params": {"mode": "difference"}, "inputs": ["a", "b"]},
    ])
    with pytest.raises(EvalError):
        ev.run(empty_diff_prog)