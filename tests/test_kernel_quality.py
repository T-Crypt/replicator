"""Kernel quality: degenerate parameters fail with a message that says how to fix them, round and shell behave on
non-box shapes, export keeps names and materials, and reverse survives bad and large files."""
import math
import time

import numpy as np
import pytest
import trimesh
from manifold3d import Manifold

from replicator.core import importers, reverse
from replicator.core.evaluate import EvalError, RawMesh, Shape, build_modifier, build_primitive
from replicator.core.export import export


def vol(kind, **p):
    return build_primitive(kind, p).volume()


def refused(kind, match, **p):
    with pytest.raises(EvalError, match=match):
        build_primitive(kind, p)


# ---------------------------------------------------------------- primitives and ops
@pytest.mark.parametrize("kind,params,match", [
    ("box", {"size": [0, 1, 1]}, "greater than 0"),
    ("sphere", {"radius": -1}, "positive"),
    ("cylinder", {"radius": float("nan"), "height": 3}, "positive"),
    ("cylinder", {"radius": 1, "height": 0}, "height"),
    ("extrude", {"points": [[0, 0], [1, 0], [0, 1]], "height": float("nan")}, "height"),
    ("revolve", {"points": [[0, 0], [0, 5], [0, 3]]}, "lies on the axis"),
    ("revolve", {"points": [[1, 0], [5, 0], [5, 5]], "degrees": 720}, "degrees"),
    ("revolve", {"points": [[1, 0], [5, 0], [float("nan"), 5]]}, "finite"),
])
def test_basic_primitives_reject_degenerate_params(kind, params, match):
    refused(kind, match, **params)


def test_loft_section_without_area_is_named():
    refused("loft", r"sections\[0\] has no area",
            sections=[{"y": 0, "points": [[0, 0], [10, 0], [5, 0]]}, {"y": 5, "radius": 4}])
    refused("loft", r"sections\[0\] radius", sections=[{"y": 0, "radius": float("nan")}, {"y": 5, "radius": 4}])


def test_loft_between_different_section_kinds_is_a_solid():
    v = vol("loft", sections=[{"y": 0, "points": [[0, 0], [10, 0], [10, 10], [0, 10]]}, {"y": 5, "radius": 4}])
    assert 5 * math.pi * 16 < v < 5 * 100


def test_pipe_duplicate_points_do_not_change_the_solid():
    a = vol("pipe", path=[[0, 0, 0], [10, 0, 0], [10, 10, 0]], radius=1, smooth=4)
    b = vol("pipe", path=[[0, 0, 0], [0, 0, 0], [10, 0, 0], [10, 0, 0], [10, 10, 0]], radius=1, smooth=4)
    assert a == pytest.approx(b, rel=1e-6)
    refused("pipe", "all the same", path=[[1, 1, 1], [1, 1, 1]], radius=1)


def test_pipe_of_two_points_with_smooth_one_is_a_capsule():
    assert vol("pipe", path=[[0, 0, 0], [10, 0, 0]], radius=1, smooth=1) > 30


def test_helix_that_needs_too_many_points_names_the_helix():
    refused("helix", "helix would need", radius=10, pitch=3, turns=200, wire_radius=1, segments=256)


@pytest.mark.parametrize("teeth", [12.5, 5, 201, "x"])
def test_gear_teeth_must_be_a_whole_number_in_range(teeth):
    refused("gear", "teeth", teeth=teeth, module=1, thickness=2)


def test_gear_bore_is_checked_against_the_root_not_the_tip():
    refused("gear", "root radius", teeth=12, module=1, thickness=2, bore=5.2)
    refused("gear", "finite", teeth=12, module=1, thickness=2, bore=float("nan"))
    solid = vol("gear", teeth=12, module=1, thickness=2)
    assert solid - vol("gear", teeth=12, module=1, thickness=2, bore=3, segments=256) == pytest.approx(
        math.pi * 3 ** 2 * 2, rel=0.01)                      # the bore was never cut before


@pytest.mark.parametrize("kind,params,match", [
    ("nozzle", {"throat_radius": 10, "expansion_ratio": 1e6}, "expansion_ratio"),
    ("nozzle", {"throat_radius": 10, "expansion_ratio": 16, "wall": 50}, "wall"),
    ("nozzle", {"throat_radius": 10, "expansion_ratio": 16, "chamber_length": 1e6}, "chamber_length"),
    ("rotor", {"hub_radius": 5, "tip_radius": 20, "chord": 500}, "chord"),
    ("rotor", {"hub_radius": 5, "tip_radius": 20, "chord": 5, "twist": 1e9}, "twist"),
    ("grille", {"size": [-10, 2, 10], "hole_size": 1}, "positive"),
])
def test_engineering_ops_reject_absurd_params(kind, params, match):
    refused(kind, match, **params)


def test_deform_refuses_a_bend_that_folds_through_itself_and_silly_twists():
    box = Manifold.cube((20, 40, 20), center=True)
    with pytest.raises(EvalError, match="too tight"):
        build_modifier("deform", {"mode": "bend", "amount": 340, "axis": "y"}, box)
    with pytest.raises(EvalError, match="twist"):
        build_modifier("deform", {"mode": "twist", "amount": 1e9}, box)


def test_wrong_typed_param_says_so():
    refused("grille", "wrong type", size=["a", 2, 10], hole_size=1)


# ---------------------------------------------------------------- round and shell
def bbox(m):
    return np.array(m.bounding_box())


def test_round_keeps_the_size_and_rounds_the_convex_edges():
    box = Manifold.cube((20, 10, 30), center=True)
    out = build_modifier("round", {"radius": 2}, box)
    assert np.allclose(bbox(out), bbox(box), atol=1e-6)
    corner_loss = (4 - math.pi) * 4 * (20 + 10 + 30) + (1 / 3) * 0  # rough: edges lose (4 - pi) r^2 per length
    assert 0 < box.volume() - out.volume() < corner_loss * 1.5


def test_round_keeps_an_l_shaped_part_in_place():
    box = Manifold.cube((20, 10, 30), center=True) + Manifold.cube((10, 30, 10)).translate((5, 0, 0))
    out = build_modifier("round", {"radius": 1.5}, box)
    assert np.allclose(bbox(out), bbox(box), atol=1e-6)
    assert 0.9 * box.volume() < out.volume() < box.volume()


def test_round_too_large_for_the_part_is_explained():
    plate = Manifold.cube((40, 2, 40), center=True)
    with pytest.raises(EvalError, match="under half the smallest size"):
        build_modifier("round", {"radius": 1.5}, plate)
    thin = sum((Manifold.cube(d, center=True) for d in ((40, 2, 2), (2, 40, 2), (2, 2, 40))), Manifold())
    with pytest.raises(EvalError, match="thinner than"):
        build_modifier("round", {"radius": 3}, thin)


def test_shell_wall_is_even_on_a_cylinder_and_a_sphere():
    cyl = build_primitive("cylinder", {"radius": 10, "height": 30})
    cavity = math.pi * 8 ** 2 * 26
    assert cyl.volume() - build_modifier("shell", {"thickness": 2}, cyl).volume() == pytest.approx(cavity, rel=0.03)
    sph = build_primitive("sphere", {"radius": 10, "segments": 64})
    cavity = 4 / 3 * math.pi * 8 ** 3
    assert sph.volume() - build_modifier("shell", {"thickness": 2}, sph).volume() == pytest.approx(cavity, rel=0.03)


def test_shell_of_an_off_centre_cone_has_a_cavity_that_does_not_poke_through():
    cone = build_primitive("cylinder", {"radius": 10, "radius_top": 2, "height": 30})
    out = build_modifier("shell", {"thickness": 2}, cone)
    assert out.status().name == "NoError"
    assert 0.3 * cone.volume() < out.volume() < 0.8 * cone.volume()
    assert np.allclose(bbox(out), bbox(cone), atol=1e-6)


# ---------------------------------------------------------------- export
def shapes_and_materials():
    cube = Manifold.cube((10, 10, 10), center=True)
    shapes = [Shape("a", "A", "Body", "steel", cube), Shape("b", "B", "Lid", "red", cube.translate((20, 0, 0)))]
    mats = {"steel": {"base_color": [0.5, 0.5, 0.5], "metalness": 1.0, "roughness": 0.3}, "red": {"base_color": [1, 0, 0]}}
    return shapes, mats


@pytest.mark.parametrize("ext", ["glb", "obj", "3mf"])
def test_export_keeps_part_names(tmp_path, ext):
    shapes, mats = shapes_and_materials()
    out = export(shapes, mats, tmp_path / f"x.{ext}")
    if ext == "obj":
        assert [ln for ln in out.read_text().splitlines() if ln.startswith("o ")] == ["o Body", "o Lid"]
    else:
        assert sorted(trimesh.load(str(out), force="scene").geometry) == ["Body", "Lid"]


def test_glb_and_obj_keep_material_names_and_colours(tmp_path):
    shapes, mats = shapes_and_materials()
    glb = trimesh.load(str(export(shapes, mats, tmp_path / "x.glb")), force="scene")
    assert {g.visual.material.name for g in glb.geometry.values()} == {"steel", "red"}
    export(shapes, mats, tmp_path / "x.obj")
    mtl = (tmp_path / "x.mtl").read_text()
    assert "newmtl steel" in mtl and "newmtl red" in mtl
    assert not (tmp_path / "material.mtl").exists()      # a shared file name made exports overwrite each other


def test_stl_and_3mf_are_z_up_and_import_back_unchanged(tmp_path):
    tall = Manifold.cube((10, 100, 20), center=True)
    for ext in ("stl", "3mf"):
        out = export([Shape("t", "T", "Tall", None, tall)], {}, tmp_path / f"t.{ext}")
        raw = trimesh.load(str(out), force="scene")
        assert [round(v) for v in raw.extents] == [10, 20, 100]
        glb, _ = importers.prepare(out, tmp_path / f"w{ext}")
        assert [round(v) for v in trimesh.load(str(glb), force="scene").extents] == [10, 100, 20]


def test_stl_accepts_separate_bodies_and_hollow_parts_and_refuses_open_surfaces_clearly(tmp_path):
    cube = Manifold.cube((10, 10, 10), center=True)
    hollow = build_modifier("shell", {"thickness": 2}, build_primitive("cylinder", {"radius": 10, "height": 30}))
    export([Shape("h", "H", "Hollow", None, hollow)], {}, tmp_path / "hollow.stl")   # genus is -1 for a cavity too
    two = cube + cube.translate((30, 0, 0))                    # genus is -1 for two bodies; that is fine to print
    export([Shape("t", "T", "Two", None, two)], {}, tmp_path / "two.stl")
    open_mesh = RawMesh(np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float), np.array([[0, 1, 2]]))
    for ext in ("stl", "3mf"):
        with pytest.raises(ValueError, match="needs closed solids.*\\['scan'\\]"):
            export([Shape("scan", "Scan", "Scan", None, open_mesh)], {}, tmp_path / f"o.{ext}")


def test_export_refuses_unknown_formats_and_empty_builds(tmp_path):
    shapes, mats = shapes_and_materials()
    with pytest.raises(ValueError, match="3mf"):
        export(shapes, mats, tmp_path / "x.step")
    with pytest.raises(ValueError, match="no visible parts"):
        export([], mats, tmp_path / "x.glb")


# ---------------------------------------------------------------- reverse and importers
def test_empty_and_broken_files_get_a_clear_message(tmp_path):
    (tmp_path / "e.glb").write_bytes(b"")
    (tmp_path / "junk.obj").write_text("this is not an obj\nf 1 2 3\n")
    for name in ("e.glb", "junk.obj"):
        with pytest.raises(ValueError, match="empty|could not be read|no triangle"):
            reverse.analyze_mesh(tmp_path / name, tmp_path / "proj")
    (tmp_path / "e.stl").write_bytes(b"")
    with pytest.raises(ValueError, match="empty"):
        importers.prepare(tmp_path / "e.stl", tmp_path / "w")


def test_too_many_triangles_is_refused_with_advice(tmp_path, monkeypatch):
    trimesh.creation.icosphere(subdivisions=3).export(tmp_path / "s.glb")
    monkeypatch.setattr(reverse, "MAX_TRIANGLES", 100)
    with pytest.raises(ValueError, match="Decimate"):
        reverse.load_pieces(tmp_path / "s.glb")


def test_instances_count_towards_the_triangle_cap(tmp_path, monkeypatch):
    scene = trimesh.Scene()
    ball = trimesh.creation.icosphere(subdivisions=1)         # 80 triangles
    for i in range(10):
        scene.add_geometry(ball, node_name=f"n{i}", geom_name="ball", transform=trimesh.transformations.translation_matrix([i * 5, 0, 0]))
    scene.export(tmp_path / "i.glb")
    monkeypatch.setattr(reverse, "MAX_TRIANGLES", 500)
    with pytest.raises(ValueError, match="Decimate"):
        reverse.load_pieces(tmp_path / "i.glb")


def test_node_transforms_are_baked_into_world_space(tmp_path):
    scene = trimesh.Scene()
    scene.add_geometry(trimesh.creation.box((2, 2, 2)), node_name="a",
                       transform=trimesh.transformations.translation_matrix([100, 0, 0]))
    scene.add_geometry(trimesh.creation.box((2, 2, 2)), node_name="b",
                       transform=trimesh.transformations.translation_matrix([-100, 0, 0]))
    scene.export(tmp_path / "t.glb")
    meshes, facts = reverse.load_pieces(tmp_path / "t.glb")
    assert sorted(round(m.bounds.mean(0)[0]) for m in meshes) == [-100, 100] and facts["triangles"] == 24


def test_a_model_under_two_units_is_flagged_as_probably_metres_not_rescaled(tmp_path):
    trimesh.creation.box((0.4, 0.2, 0.1)).export(tmp_path / "small.glb")
    program, report = reverse.analyze_mesh(tmp_path / "small.glb", tmp_path / "proj")
    hint = next(e for e in report["ledger"] if "metres" in e["claim"])
    assert hint["kind"] == "inferred" and "did not rescale" in hint["claim"]
    assert report["ledger"][next(i for i, e in enumerate(report["ledger"]) if e is hint) - 1]["claim"].startswith(
        "overall size 0.4")                                     # the measurement is untouched
    assert program["units"] == "mm"


def test_stl_size_is_taken_as_millimetres_by_convention(tmp_path):
    trimesh.creation.box((40, 20, 10)).export(tmp_path / "p.stl")
    _, report = reverse.analyze_mesh(tmp_path / "p.stl", tmp_path / "proj")
    assert any(e["claim"] == "units are millimetres" and e["kind"] == "inferred" for e in report["ledger"])


def test_two_thousand_pieces_import_in_seconds(tmp_path):
    rng = np.random.default_rng(1)
    scene = trimesh.Scene()
    for i in range(2000):
        box = trimesh.creation.box((1 + rng.random(), 1 + rng.random(), 1 + rng.random()))
        box.apply_translation(rng.random(3) * 60)
        scene.add_geometry(box, node_name=f"n{i}")
    scene.export(tmp_path / "big.glb")
    t = time.perf_counter()
    program, _ = reverse.analyze_mesh(tmp_path / "big.glb", tmp_path / "proj")
    assert len(program["ops"]) == reverse.MAX_PIECES
    assert time.perf_counter() - t < 15
