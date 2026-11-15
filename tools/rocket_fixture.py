"""Writes replicator/fixtures/rocket_engine.json: a gas-generator rocket engine laid out from the nozzle's real contour.

Every position is derived from the thrust chamber (throat radius 100 mm, expansion ratio 16, contraction ratio 4), so
the turbopump, manifold, lines and frame land where they would on a real engine. Run it, then check the result with
the critic: `.venv/bin/python -m tools.rocket_fixture`.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from replicator import FIXTURES
from replicator.core import assembly, critique, materials
from replicator.core.evaluate import Evaluator
from replicator.core.ops_engineering import nozzle_contour

RT, EPS, CR, WALL = 100.0, 16.0, 4.0, 6.0
OUT = FIXTURES / "rocket_engine.json"

inner = nozzle_contour(RT, EPS, CR, None, 0.8)
x_top, x_exit = inner[0, 0] - WALL, inner[-1, 0]
height = x_exit - x_top
lift = height / 2 + 40                       # exit plane 40 mm above the floor (engine on its stand)


def y_of(x: float) -> float:
    return -(x - (x_top + x_exit) / 2) + lift


def r_at(x: float) -> float:
    return float(np.interp(x, inner[:, 0], inner[:, 1])) + WALL


TOP = y_of(x_top)
RC = RT * math.sqrt(CR) + WALL
X_MAN = 0.35 * x_exit
Y_MAN, R_MAN = y_of(X_MAN), r_at(X_MAN)
PX, PZ = RC + 230, 0.0                       # turbopump axis, beside the chamber
Y_FUEL, Y_LOX, Y_TURB = TOP - 470, TOP - 250, TOP - 70

ops = [
    {"id": "chamber", "op": "nozzle", "label": "Thrust Chamber and Bell Nozzle", "component": "chamber",
     "material": "inconel_718",
     "params": {"throat_radius": RT, "expansion_ratio": EPS, "contraction_ratio": CR, "wall": WALL,
                "segments": 128, "translate": [0, lift, 0]}},
    {"id": "dome", "op": "revolve", "label": "Injector Dome", "component": "injector", "material": "steel_maraging",
     "params": {"points": [[0, 0]] + [[RC * math.cos(a), 110 * math.sin(a)] for a in np.linspace(0, math.pi / 2, 12)],
                "segments": 96, "translate": [0, TOP, 0]}},
    {"id": "frame", "op": "tube", "label": "Thrust Cone", "component": "frame", "material": "titanium_ti6al4v",
     "params": {"height": 150, "radius": 150, "radius_top": 48, "wall": 8, "translate": [0, TOP + 150, 0]}},
    {"id": "gimbal", "op": "sphere", "label": "Gimbal Bearing", "component": "gimbal", "material": "steel",
     "params": {"radius": 46, "translate": [0, TOP + 250, 0]}},
    {"id": "gimbal_pad", "op": "box", "label": "Gimbal Mount Pad", "component": "gimbal", "material": "titanium_ti6al4v",
     "params": {"size": [180, 30, 180], "translate": [0, TOP + 300, 0]}},
    {"id": "gimbal_set", "op": "group", "inputs": ["gimbal", "gimbal_pad"], "label": "Gimbal Assembly",
     "component": "gimbal"},
    {"id": "manifold", "op": "torus", "label": "Coolant Inlet Manifold", "component": "manifold", "material": "steel",
     "params": {"major_radius": R_MAN + 22, "minor_radius": 24, "segments": 96, "translate": [0, Y_MAN, 0]}},
    {"id": "band", "op": "torus", "label": "Bell Stiffener Band", "component": "manifold", "material": "inconel_718",
     "params": {"major_radius": r_at(0.75 * x_exit) + 6, "minor_radius": 8, "segments": 128,
                "translate": [0, y_of(0.75 * x_exit), 0]}},
]
for name, y, label in (("fuel", Y_FUEL, "Fuel Pump"), ("lox", Y_LOX, "Oxidizer Pump")):
    ops += [
        {"id": f"{name}_body", "op": "cylinder", "label": f"{label} Body", "component": "turbopump",
         "material": "aluminium_7075", "params": {"height": 150, "radius": 92, "translate": [PX, y, PZ]}},
        {"id": f"{name}_volute", "op": "torus", "label": f"{label} Volute", "component": "turbopump",
         "material": "aluminium_7075", "params": {"major_radius": 100, "minor_radius": 38, "translate": [PX, y, PZ]}},
        {"id": f"{name}_pump", "op": "boolean", "inputs": [f"{name}_body", f"{name}_volute"],
         "params": {"mode": "union"}, "label": label, "component": "turbopump"},
    ]
ops += [
    {"id": "shaft", "op": "cylinder", "label": "Turbopump Shaft Housing", "component": "turbopump",
     "material": "steel_maraging", "params": {"height": Y_TURB - Y_FUEL - 25, "radius": 44,
                                              "translate": [PX, (Y_TURB - 55 + Y_FUEL - 30) / 2, PZ]}},
    {"id": "turbine", "op": "tube", "label": "Turbine Housing", "component": "turbine", "material": "inconel_heat",
     "params": {"height": 110, "radius": 104, "wall": 12, "translate": [PX, Y_TURB, PZ]}},
    {"id": "turbine_disc", "op": "rotor", "label": "Turbine Wheel", "component": "turbine", "material": "inconel_718",
     "params": {"hub_radius": 40, "tip_radius": 90, "chord": 26, "blades": 31, "pitch": 55, "twist": 10,
                "hub_length": 40, "translate": [PX, Y_TURB, PZ]}},
    {"id": "gg", "op": "capsule", "label": "Gas Generator", "component": "gas_generator", "material": "inconel_heat",
     "params": {"height": 150, "radius": 46, "translate": [PX, Y_TURB + 150, PZ - 150]}},
    {"id": "gg_line", "op": "pipe", "label": "Gas Generator Hot-Gas Line", "component": "gas_generator",
     "material": "inconel_heat",
     "params": {"path": [[PX, Y_TURB + 150, PZ - 150], [PX, Y_TURB + 120, PZ - 60], [PX, Y_TURB + 50, PZ]],
                "radius": 26, "smooth": 8}},
    {"id": "exhaust", "op": "pipe", "label": "Turbine Exhaust Duct", "component": "exhaust", "material": "inconel_heat",
     "params": {"path": [[PX + 100, Y_TURB, PZ], [PX + 160, Y_TURB - 70, PZ + 20], [PX + 175, Y_MAN, PZ + 40],
                         [PX + 175, lift + 60, PZ + 40]],
                "radius": 52, "smooth": 10}},
    {"id": "fuel_line", "op": "pipe", "label": "Fuel Line to Coolant Manifold", "component": "feed_lines",
     "material": "steel",
     "params": {"path": [[PX - 80, Y_FUEL, PZ + 60], [PX - 120, Y_FUEL - 120, PZ + 140], [R_MAN + 80, Y_MAN + 40, 160],
                         [(R_MAN + 22) * 0.9, Y_MAN, (R_MAN + 22) * 0.44]],
                "radius": 34, "smooth": 10}},
    {"id": "lox_line", "op": "pipe", "label": "Oxidizer Line to Injector", "component": "feed_lines",
     "material": "steel",
     "params": {"path": [[PX - 80, Y_LOX, PZ - 50], [PX - 160, Y_LOX + 80, PZ - 120], [RC * 0.9, TOP + 40, -120],
                         [RC * 0.55, TOP + 75, -60]],
                "radius": 38, "smooth": 10}},
    {"id": "lox_valve", "op": "cylinder", "label": "Main Oxidizer Valve", "component": "feed_lines",
     "material": "aluminium_7075_black",
     "params": {"height": 110, "radius": 52, "rotate": [0, 0, 90], "translate": [PX - 140, Y_LOX + 60, PZ - 100]}},
]
for k, (ax, az) in enumerate(((RC + 30, 0), (0, RC + 30))):
    ops += [
        {"id": f"actuator_{k}", "op": "capsule", "label": f"Gimbal Actuator {'AB'[k]}", "component": "actuators",
         "material": "aluminium_7075_black",
         "params": {"height": 330, "radius": 24, "translate": [-ax if k == 0 else 0, TOP - 40, -az if k else 0]}},
    ]

used = sorted({o["material"] for o in ops if "material" in o})
program = {
    "version": 1, "name": "Gas-Generator Rocket Engine", "units": "mm",
    "materials": {m: dict(materials.PRESETS[m][2]) for m in used},
    "components": [{"id": c, "label": l} for c, l in (
        ("chamber", "Thrust Chamber"), ("injector", "Injector"), ("frame", "Thrust Frame"), ("gimbal", "Gimbal"),
        ("manifold", "Coolant Manifold"), ("turbopump", "Turbopump"), ("turbine", "Turbine"),
        ("gas_generator", "Gas Generator"), ("exhaust", "Turbine Exhaust"), ("feed_lines", "Feed Lines"),
        ("actuators", "Gimbal Actuators"))],
    "blueprint": {
        "title": "Gas-Generator Rocket Engine",
        "summary": f"A sea-level kerosene and liquid-oxygen engine laid out from its thrust chamber: throat radius "
                   f"{RT:.0f} mm, expansion ratio {EPS:.0f}, contraction ratio {CR:.0f}, an 80 % Rao bell. A single "
                   "turbopump beside the chamber is driven by a gas generator and dumps its exhaust through a duct.",
        "dimensions": None,
        "parts": [{"name": c["label"]} for c in []],
    },
    "ops": ops,
}
shapes = Evaluator().step(program)
lo = np.min([s.manifold.bounding_box()[:3] for s in shapes], axis=0)
hi = np.max([s.manifold.bounding_box()[3:] for s in shapes], axis=0)
program["blueprint"]["dimensions"] = [round(float(v)) for v in hi - lo]
found = critique.critique(program, shapes, assembly.components(program, shapes))
OUT.write_text(json.dumps(program, indent=1))
print(f"wrote {OUT.name}: {len(ops)} ops, {len(shapes)} parts, {program['blueprint']['dimensions']} mm")
for i in found:
    print(f"  {i.severity} {i.kind} {i.subject}: {i.message}")
