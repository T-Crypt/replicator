import math
import os
import sys
import numpy as np
import pytest
from manifold3d import Manifold, OpType

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from replicator.core.evaluate import EvalError
from replicator.core import ops_advanced


def _require(m, name):
    assert not m.is_empty(), f"{name}: empty manifold"
    assert float(m.volume()) > 0, f"{name}: non-positive volume"
    return m


def test_loft_two_circles_close_to_cylinder():
    r, h = 10.0, 50.0
    m = ops_advanced.PRIMITIVES["loft"][2]({"segments": 48, "sections": [
        {"y": 0.0, "radius": r},
        {"y": h, "radius": r},
    ]})
    _require(m, "loft cylinder")
    expected = math.pi * r * r * h
    assert abs(m.volume() - expected) / expected < 0.03


def test_loft_bad_sections_raise():
    with pytest.raises(EvalError):
        ops_advanced.PRIMITIVES["loft"][2]({"sections": [{"y": 0.0, "radius": 1.0}]})


def test_pipe_straight_capsule_volume():
    r, length = 5.0, 40.0
    m = ops_advanced.PRIMITIVES["pipe"][2]({"path": [[0, 0, 0], [0, length, 0]], "radius": r, "segments": 20})
    _require(m, "pipe capsule")
    expected = math.pi * r * r * length + (4.0 / 3.0) * math.pi * r ** 3
    assert abs(m.volume() - expected) / expected < 0.05


def test_helix_wire_volume_rough():
    r = 10.0
    pitch = 10.0
    turns = 2.0
    wr = 2.0
    m = ops_advanced.PRIMITIVES["helix"][2]({
        "radius": r,
        "pitch": pitch,
        "turns": turns,
        "wire_radius": wr,
        "segments": 24,
    })
    _require(m, "helix")
    length = turns * math.sqrt((2 * math.pi * r) ** 2 + pitch ** 2)
    expected = math.pi * wr ** 2 * length
    assert abs(m.volume() - expected) / expected < 0.08


def test_gear_volume_between_disks():
    teeth = 12
    module = 2.0
    thickness = 5.0
    ra = module * teeth / 2.0 + module
    rb = module * teeth / 2.0 - 1.25 * module
    m = ops_advanced.MODIFIERS["deform"][2] if False else ops_advanced.PRIMITIVES["gear"][2]({
        "teeth": teeth,
        "module": module,
        "thickness": thickness,
        "segments": 128,
    })
    _require(m, "gear")
    v = float(m.volume())
    assert v >= math.pi * rb * rb * thickness - 1e-6
    assert v <= math.pi * ra * ra * thickness + 1e-6


def test_gear_too_few_teeth_raise():
    with pytest.raises(EvalError):
        ops_advanced.PRIMITIVES["gear"][2]({"teeth": 3, "module": 2.0, "thickness": 5.0})


def test_deform_taper_low_volume():
    box = Manifold.cube([20.0, 40.0, 20.0], center=True).rotate([-90.0, 0.0, 0.0])
    # box along Y is already 40 in Y? cube size [20,40,20] center true is Y-extent 40.
    v0 = float(box.volume())
    m = ops_advanced.MODIFIERS["deform"][2]({"mode": "taper", "amount": 0.5, "axis": "y", "resolution": 1.0}, box)
    _require(m, "taper")
    assert float(m.volume()) < v0


def test_deform_twist_volume_conserved():
    box = Manifold.cube([10.0, 30.0, 10.0], center=True)
    v0 = float(box.volume())
    m = ops_advanced.MODIFIERS["deform"][2]({"mode": "twist", "amount": 45.0, "axis": "y", "resolution": 0.75}, box)
    _require(m, "twist")
    assert abs(float(m.volume()) - v0) / v0 < 0.02


def test_deform_bend_box_volume_and_bbox():
    box = Manifold.cube([10.0, 40.0, 10.0], center=True)
    v0 = float(box.volume())
    b0 = np.asarray(box.bounding_box())
    m = ops_advanced.MODIFIERS["deform"][2]({"mode": "bend", "amount": 60.0, "axis": "y", "resolution": 0.75}, box)
    _require(m, "bend")
    assert abs(float(m.volume()) - v0) / v0 < 0.05
    b1 = np.asarray(m.bounding_box())
    # Bending a box should change at least one bounding extent.
    e0 = b1[3:] - b1[:3]
    e1 = b0[3:] - b0[:3]
    assert np.any(np.abs(e0 - e1) > 1e-3)


def test_deform_unknown_mode_raise():
    box = Manifold.cube([10.0, 10.0, 10.0], center=True)
    with pytest.raises(EvalError):
        ops_advanced.MODIFIERS["deform"][2]({"mode": "squish", "amount": 0.5}, box)
