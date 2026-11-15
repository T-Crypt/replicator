import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from replicator.core import physics, robot
from replicator.core.evaluate import Evaluator
from replicator.core.program import check

FIX = Path(__file__).parent.parent / "fixtures"
BOX = {"version": 1, "name": "Steel block", "units": "mm",
       "materials": {"steel": {"base_color": [0.6, 0.6, 0.6]}, "glow": {"base_color": [0.2, 0.8, 1.0]}},
       "components": [{"id": "block", "label": "Block"}, {"id": "lamp", "label": "Lamp"}],
       "ops": [{"id": "b", "op": "box", "component": "block", "material": "steel",
                "params": {"size": [100, 20, 50], "translate": [0, 10, 0]}},
               {"id": "l", "op": "sphere", "component": "lamp", "material": "glow",
                "params": {"radius": 5, "translate": [0, 40, 0]}}]}


def _build(program):
    program = check(json.loads(json.dumps(program)))
    return program, Evaluator().step(program)


def test_urdf_carries_the_measured_mass_centre_and_box_inertia_in_z_up_metres(tmp_path):
    prog, shapes = _build(BOX)
    f = robot.write(prog, shapes, tmp_path / "block.urdf")
    root = ET.parse(f).getroot()
    block = root.find("link[@name='block']")
    assert float(block.find("inertial/mass").get("value")) == pytest.approx(0.785, rel=1e-6)
    assert [float(v) for v in block.find("inertial/origin").get("xyz").split()] == pytest.approx([0, 0, 0.010], abs=1e-9)
    i = block.find("inertial/inertia")
    m = 0.785
    assert float(i.get("ixx")) == pytest.approx(m / 12 * (0.05 ** 2 + 0.02 ** 2), rel=1e-6)
    assert float(i.get("iyy")) == pytest.approx(m / 12 * (0.1 ** 2 + 0.02 ** 2), rel=1e-6)
    assert float(i.get("izz")) == pytest.approx(m / 12 * (0.1 ** 2 + 0.05 ** 2), rel=1e-6)
    assert float(i.get("ixy")) == pytest.approx(0, abs=1e-12)
    assert root.find("joint[@name='block_fixed']").get("type") == "fixed"
    assert (tmp_path / "meshes" / "block.stl").exists()


def test_a_glow_part_keeps_its_mesh_but_has_no_inertial(tmp_path):
    prog, shapes = _build(BOX)
    root = ET.parse(robot.write(prog, shapes, tmp_path / "block.urdf")).getroot()
    lamp = root.find("link[@name='lamp']")
    assert lamp.find("inertial") is None and lamp.find("visual/geometry/mesh") is not None


def test_urdf_and_mjcf_agree_with_the_status_bar_mass_on_a_real_fixture(tmp_path):
    prog, shapes = _build(json.loads((FIX / "quadcopter_drone.json").read_text()))
    total = physics.body(prog, shapes).kg
    urdf = ET.parse(robot.write(prog, shapes, tmp_path / "d.urdf")).getroot()
    mjcf = ET.parse(robot.write(prog, shapes, tmp_path / "d.xml")).getroot()
    assert sum(float(m.get("value")) for m in urdf.iter("mass")) == pytest.approx(total, rel=1e-6)
    assert sum(float(b.get("mass")) for b in mjcf.iter("inertial")) == pytest.approx(total, rel=1e-6)


def test_link_names_are_unique_and_safe_for_xml_ids():
    prog = dict(BOX, components=[{"id": "1 arm", "label": "x"}, {"id": "base", "label": "y"}],
                ops=[dict(BOX["ops"][0], component="1 arm"), dict(BOX["ops"][1], component="base", material="steel")])
    prog, shapes = _build(prog)
    assert [l.name for l in robot.links(prog, shapes)] == ["p_1_arm", "base_2"]


def test_mujoco_loads_the_mjcf_and_the_model_comes_to_rest_upright(tmp_path):
    mujoco = pytest.importorskip("mujoco")
    prog, shapes = _build(json.loads((FIX / "raspberry_pi_5.json").read_text()))
    m = mujoco.MjModel.from_xml_path(str(robot.write(prog, shapes, tmp_path / "pi.xml")))
    d = mujoco.MjData(m)
    for _ in range(int(1.0 / m.opt.timestep)):
        mujoco.mj_step(m, d)
    assert m.body_mass.sum() == pytest.approx(physics.body(prog, shapes).kg, rel=1e-6)
    assert abs(d.qpos[3]) > 0.9999          # quaternion w: under ~1.6 degrees of tilt
