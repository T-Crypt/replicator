"""STEP export: closed shells, voids kept, volume exact through OpenCASCADE's own reader."""
import pytest
from manifold3d import Manifold

from replicator.core import step
from replicator.core.evaluate import Shape


def _shapes():
    hollow = Manifold.cube((10, 10, 10), True) - Manifold.cube((4, 4, 4), True)       # 936 mm3, one cavity
    two = Manifold.cube((5, 5, 5)) + Manifold.cube((5, 5, 5)).translate((20, 0, 0))    # two lumps, 250 mm3
    tube = Manifold.cylinder(30, 8, 8, 48) - Manifold.cylinder(30, 5, 5, 48)          # a through hole: inner bound
    return [Shape("a", "Hollow cube", "a", None, hollow), Shape("b", "Two blocks", "b", None, two),
            Shape("c", "Tube", "c", None, tube)], hollow.volume() + two.volume() + tube.volume()


def test_step_file_is_well_formed(tmp_path):
    shapes, _ = _shapes()
    text = step.write(shapes, tmp_path / "t.step").read_text()
    assert text.startswith("ISO-10303-21;") and text.rstrip().endswith("END-ISO-10303-21;")
    assert text.count("MANIFOLD_SOLID_BREP(") == 3 and text.count("BREP_WITH_VOIDS(") == 1
    assert "AUTOMOTIVE_DESIGN" in text and "SI_UNIT(.MILLI.,.METRE.)" in text
    assert text.count("ADVANCED_FACE(") < 6 + 6 + 6 + 2 * 48 + 2 * 46       # coplanar triangles merged into faces


def test_open_surfaces_are_refused(tmp_path):
    class Raw:      # an imported surface, like evaluate.RawMesh: no status(), cannot be a solid
        pass
    with pytest.raises(ValueError, match="closed solids"):
        step.write([Shape("x", "Sheet", "x", None, Raw())], tmp_path / "x.step")


def test_occt_reads_valid_solids_with_exact_volume(tmp_path):
    occ = pytest.importorskip("OCP.STEPControl")
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.IFSelect import IFSelect_RetDone
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS
    shapes, volume = _shapes()
    r = occ.STEPControl_Reader()
    assert r.ReadFile(str(step.write(shapes, tmp_path / "t.step"))) == IFSelect_RetDone
    r.TransferRoots()
    ex, n, total = TopExp_Explorer(r.OneShape(), TopAbs_SOLID), 0, 0.0
    while ex.More():
        s = TopoDS.Solid(ex.Current())
        assert BRepCheck_Analyzer(s).IsValid()
        g = GProp_GProps()
        BRepGProp.VolumeProperties_s(s, g)
        total += g.Mass()
        n += 1
        ex.Next()
    assert n == 4                       # hollow cube (with its void), two blocks, tube
    assert total == pytest.approx(volume, rel=1e-6)


def test_a_sliver_triangle_does_not_open_the_shell(tmp_path):
    """Regression: the rocket engine's gimbal actuator (a capsule 1.5 m up) has a zero-area triangle on its seam; it
    used to be dropped, leaving a hole, and OpenCASCADE read the part as an open shell with no volume."""
    occ = pytest.importorskip("OCP.STEPControl")
    from OCP.BRepGProp import BRepGProp
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from replicator.core.evaluate import Evaluator
    from replicator.core.program import check
    prog = check({"version": 1, "name": "a", "units": "mm", "materials": {}, "ops": [
        {"id": "act", "op": "capsule", "params": {"height": 330, "radius": 24, "translate": [-236.0, 1515.0896534380868, 0]}}]})
    shapes = Evaluator(tmp_path).step(prog)
    r = occ.STEPControl_Reader()
    r.ReadFile(str(step.write(shapes, tmp_path / "a.step")))
    r.TransferRoots()
    ex = TopExp_Explorer(r.OneShape(), TopAbs_SOLID)
    assert ex.More(), "read back as an open shell, not a solid"
    g = GProp_GProps()
    BRepGProp.VolumeProperties_s(ex.Current(), g)
    assert g.Mass() == pytest.approx(shapes[0].manifold.volume(), rel=1e-6)
