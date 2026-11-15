import zipfile

import pytest
import trimesh

from replicator.core import importers, reverse


def tall_box_zup(path):
    trimesh.creation.box(extents=[10, 20, 100]).export(path)   # 100 tall along Z, as a slicer stores it


def extents(glb):
    return [round(v) for v in trimesh.load(str(glb), force="scene").extents]


def test_stl_from_a_printer_comes_in_y_up(tmp_path):
    tall_box_zup(tmp_path / "part.stl")
    glb, what = importers.prepare(tmp_path / "part.stl", tmp_path / "w")
    assert what == "STL (3D printing)"
    assert extents(glb) == [10, 100, 20]


def test_3mf_is_read_and_turned_y_up(tmp_path):
    trimesh.Scene(trimesh.creation.box(extents=[10, 20, 100])).export(tmp_path / "plate.3mf")
    glb, _ = importers.prepare(tmp_path / "plate.3mf", tmp_path / "w")
    assert extents(glb) == [10, 100, 20]


def test_gallery_zip_merges_its_model_files_and_ignores_the_rest(tmp_path):
    tall_box_zup(tmp_path / "a.stl")
    trimesh.creation.icosphere(radius=5).apply_translation([50, 0, 0]).export(tmp_path / "b.stl")
    with zipfile.ZipFile(tmp_path / "thing.zip", "w") as z:
        z.write(tmp_path / "a.stl", "files/a.stl")
        z.write(tmp_path / "b.stl", "files/b.stl")
        z.writestr("images/photo.jpg", b"not a model")
        z.writestr("README.txt", "print at 0.2 mm")
    glb, what = importers.prepare(tmp_path / "thing.zip", tmp_path / "w")
    assert what == "ZIP bundle: 2 STL (3D printing) file(s)"
    meshes, _ = reverse.load_pieces(glb)
    assert len(meshes) == 2


def test_archive_entries_cannot_escape_their_folder(tmp_path):
    with zipfile.ZipFile(tmp_path / "evil.zip", "w") as z:
        z.writestr("../../outside.stl", b"solid x\nendsolid x\n")
    with pytest.raises(ValueError, match="outside its folder"):
        importers.prepare(tmp_path / "evil.zip", tmp_path / "w")
    assert not (tmp_path / "outside.stl").exists()


def test_unknown_formats_are_refused_with_the_supported_list(tmp_path):
    with pytest.raises(ValueError, match=r"\.xyz is not a 3D format"):
        importers.route(tmp_path / "cloud.xyz")


def test_a_real_step_part_arrives_welded_and_in_millimetres(tmp_path):
    pytest.importorskip("cascadio")
    from pathlib import Path
    step = Path(__file__).parent / "data" / "featuretype.STEP"
    glb, what = importers.prepare(step, tmp_path / "w")
    part = trimesh.load(str(glb), force="scene").to_geometry()
    assert what == "STEP (CAD)"
    assert [round(float(v), 1) for v in part.extents] == [127.0, 63.5, 34.9]
    assert part.is_watertight and round(part.volume / 1000) == 191
    meshes, _ = reverse.load_pieces(glb)
    assert len(meshes) == 1
