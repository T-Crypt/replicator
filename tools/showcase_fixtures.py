"""Writes the two showcase fixtures from real dimensions: replicator/fixtures/raspberry_pi_5.json and replicator/fixtures/gaming_pc_liquid.json.

Every position is worked out here (board outline, connector pitches, case panels, fan and radiator sizes, the
coolant loop's ports), not dreamed, so the parts touch where they should and nothing passes through anything:

    .venv/bin/python -m tools.showcase_fixtures && .venv/bin/python -m tools.check replicator/fixtures/raspberry_pi_5.json replicator/fixtures/gaming_pc_liquid.json

Pi 5 positions follow the published mechanical drawing (85 x 56 mm board, M2.5 holes on a 58 x 49 mm pattern 3.5 mm
in from the edges). Connector bodies are simplified boxes at their real footprint and height.
"""
from __future__ import annotations

from replicator import FIXTURES
import json
from pathlib import Path

FIX = FIXTURES


def box(oid, label, comp, mat, lo, hi, **extra):
    """An axis-aligned box from its min and max corners (mm)."""
    size = [round(h - l, 3) for l, h in zip(lo, hi)]
    centre = [round((l + h) / 2, 3) for l, h in zip(lo, hi)]
    return {"id": oid, "op": "box", "label": label, "component": comp, "material": mat,
            "params": {"size": size, "translate": centre, **extra}}


def cyl(oid, label, comp, mat, r, h, at, axis="y", **extra):
    rot = {"y": [0, 0, 0], "x": [0, 0, 90], "z": [90, 0, 0]}[axis]
    return {"id": oid, "op": "cylinder", "label": label, "component": comp, "material": mat,
            "params": {"radius": r, "height": h, "rotate": rot, "translate": list(at), "segments": 48, **extra}}


def union(oid, label, comp, inputs, mat=None):
    op = {"id": oid, "op": "boolean", "label": label, "component": comp, "inputs": inputs, "params": {"mode": "union"}}
    if mat:
        op["material"] = mat
    return op


def cut(oid, label, comp, inputs, mat=None):
    op = {"id": oid, "op": "boolean", "label": label, "component": comp, "inputs": inputs,
          "params": {"mode": "difference"}}
    if mat:
        op["material"] = mat
    return op


# ------------------------------------------------------------------ Raspberry Pi 5
def raspberry_pi() -> dict:
    L, W, T = 85.0, 56.0, 1.6          # board, X along the long edge, Z across, Y up
    S = 6.0                            # standoff height: board underside sits 6 mm above the desk
    y0, y1 = S, S + T                  # board bottom and top
    x = lambda v: v - L / 2            # drawing coordinates (origin at the board corner) to centred
    z = lambda v: v - W / 2
    ops = []
    holes = [(3.5, 3.5), (61.5, 3.5), (3.5, 52.5), (61.5, 52.5)]
    ops.append(box("pcb_blank", "PCB blank", "board", "pcb_green", [x(0), y0, z(0)], [x(L), y1, z(W)]))
    for i, (hx, hz) in enumerate(holes):
        ops.append(cyl(f"hole{i}", "Mounting hole", "board", "pcb_green", 1.35, 4, [x(hx), (y0 + y1) / 2, z(hz)]))
    ops.append(cut("pcb", "PCB, 85 x 56 mm, M2.5 holes on 58 x 49", "board",
                   ["pcb_blank", "hole0", "hole1", "hole2", "hole3"]))
    for i, (hx, hz) in enumerate(holes):
        ops.append(cyl(f"standoff{i}", "M2.5 brass standoff", "standoffs", "brass", 2.5, S, [x(hx), S / 2, z(hz)],
                       segments=6))
    ops.append(union("standoffs", "Four M2.5 standoffs", "standoffs", [f"standoff{i}" for i in range(4)]))

    # SoC and RAM under the active cooler
    ops.append(box("soc", "BCM2712 SoC (heat spreader)", "soc", "silicon_package",
                   [x(21), y1, z(23)], [x(38), y1 + 1.2, z(40)]))
    ops.append(box("ram", "LPDDR4X SDRAM", "soc", "silicon_package", [x(41), y1, z(25)], [x(53), y1 + 1.0, z(39)]))
    ops.append(box("rp1", "RP1 I/O controller", "soc", "silicon_package", [x(60), y1, z(29)], [x(67), y1 + 0.9, z(36)]))
    # active cooler: finned aluminium sink on the SoC, blower fan beside the fins
    cy = y1 + 1.2
    ops.append(box("sink_base", "Heatsink base plate", "cooler", "aluminium_6063", [x(17), cy, z(14)], [x(54), cy + 2, z(48)]))
    ops.append(box("fin", "Heatsink fin", "cooler", "aluminium_6063", [x(17), cy + 2, z(14)], [x(17.8), cy + 7.5, z(30)]))
    ops.append({"id": "fins", "op": "array", "input": "fin", "label": "Heatsink, 18 fins", "component": "cooler",
                "material": "aluminium_6063", "params": {"mode": "linear", "count": 18, "offset": [2.06, 0, 0]}})
    ops.append(box("fan_frame_blank", "Blower housing", "cooler", "plastic_black", [x(29), cy + 2, z(31)], [x(51), cy + 7.5, z(48)]))
    ops.append(cyl("fan_bore", "Blower intake", "cooler", "plastic_black", 7.6, 8, [x(40), cy + 6, z(39.5)]))
    ops.append(cut("fan_housing", "Blower fan housing", "cooler", ["fan_frame_blank", "fan_bore"]))
    ops.append({"id": "fan_rotor", "op": "rotor", "label": "Blower impeller", "component": "cooler", "material": "plastic_black",
                "params": {"hub_radius": 2.8, "tip_radius": 7.2, "chord": 2.6, "blades": 11, "pitch": 30, "twist": 5,
                           "hub_length": 3.0, "translate": [x(40), cy + 3.5, z(39.5)]}})
    # GPIO header: 2 x 20 pins at 2.54 mm along the far long edge
    gx0, gz0 = 7.1, 50.9
    ops.append(box("gpio_base", "GPIO header body", "gpio", "plastic_black",
                   [x(gx0 - 1.27), y1, z(gz0 - 1.27)], [x(gx0 + 19 * 2.54 + 1.27), y1 + 2.5, z(gz0 + 2.54 + 1.27)]))
    ops.append(box("pin", "Header pin", "gpio", "brass_gold_plated",
                   [x(gx0 - 0.32), y1 + 2.5, z(gz0 - 0.32)], [x(gx0 + 0.32), y1 + 8.5, z(gz0 + 0.32)]))
    ops.append({"id": "pin_row", "op": "array", "input": "pin", "label": "Pin row", "component": "gpio",
                "material": "brass_gold_plated", "params": {"mode": "linear", "count": 20, "offset": [2.54, 0, 0]}})
    ops.append({"id": "pins", "op": "array", "input": "pin_row", "label": "40 GPIO pins", "component": "gpio",
                "material": "brass_gold_plated", "params": {"mode": "linear", "count": 2, "offset": [0, 0, 2.54]}})
    # right edge: Ethernet and two stacked USB pairs, overhanging the board edge by 2-3 mm
    # port bodies are drawn sheet-metal boxes: shelled to 0.4 mm so their mass is a shell's, not a steel brick's
    for oid, label, lo, hi in (("eth", "Gigabit Ethernet jack", [x(66), y1, z(2.5)], [x(87.5), y1 + 13.5, z(18.5)]),
                               ("usb3", "USB 3.0 pair (blue)", [x(70), y1, z(21.6)], [x(87.5), y1 + 16, z(36.6)]),
                               ("usb2", "USB 2.0 pair", [x(70), y1, z(39.8)], [x(87.5), y1 + 16, z(54.8)])):
        ops.append(box(f"{oid}_solid", label, "ports", "steel_shell", lo, hi))
        ops.append({"id": oid, "op": "shell", "input": f"{oid}_solid", "label": label, "component": "ports",
                    "material": "steel_shell", "params": {"thickness": 0.4}})
    # near long edge: USB-C power, two micro HDMI, the power button
    ops.append(box("usbc", "USB-C power input", "ports", "steel_shell", [x(7.1), y1, z(-1)], [x(16.1), y1 + 3.2, z(6.5)]))
    ops.append(box("hdmi0", "Micro HDMI 0", "ports", "steel_shell", [x(22.6), y1, z(-1)], [x(29.1), y1 + 3.5, z(6.5)]))
    ops.append(box("hdmi1", "Micro HDMI 1", "ports", "steel_shell", [x(36.0), y1, z(-1)], [x(42.5), y1 + 3.5, z(6.5)]))
    ops.append(box("button", "Power button", "ports", "plastic_black", [x(0.5), y1, z(10)], [x(4.5), y1 + 2.5, z(14)]))
    # FPC connectors: two MIPI camera/display, PCIe on the left short edge
    ops.append(box("mipi0", "MIPI camera/display 0", "connectors", "plastic_white", [x(45.5), y1, z(1.5)], [x(48.5), y1 + 4, z(14)]))
    ops.append(box("mipi1", "MIPI camera/display 1", "connectors", "plastic_white", [x(49.5), y1, z(1.5)], [x(52.5), y1 + 4, z(14)]))
    ops.append(box("pcie", "PCIe 2.0 x1 FPC connector", "connectors", "plastic_white", [x(1.0), y1, z(20)], [x(4.5), y1 + 2.5, z(36)]))
    ops.append(box("fan_hdr", "Fan header", "connectors", "plastic_white", [x(57), y1, z(43)], [x(62), y1 + 3, z(46)]))
    ops.append(box("sd", "microSD card slot (underside)", "connectors", "steel_shell", [x(0), y0 - 1.4, z(20.5)], [x(14), y0, z(35.5)]))
    ops.append(box("sd_card", "microSD card", "connectors", "plastic_black", [x(-2.5), y0 - 1.2, z(22.5)], [x(0), y0 - 0.2, z(33.5)]))
    return {
        "version": 1, "name": "Raspberry Pi 5", "units": "mm",
        "summary": "A Raspberry Pi 5 at real scale on four M2.5 standoffs: BCM2712 under the active cooler, LPDDR4X, "
                   "the RP1 I/O chip, 40-pin GPIO, Ethernet, two USB 3 and two USB 2, USB-C power, two micro HDMI, "
                   "two MIPI connectors, PCIe FPC and microSD.",
        "components": [{"id": i, "label": l, "role": r} for i, l, r in (
            ("board", "PCB", "85 x 56 mm FR-4, 1.6 mm"), ("standoffs", "Standoffs", "M2.5 brass, 6 mm"),
            ("soc", "SoC, RAM and RP1", "BCM2712, LPDDR4X, RP1 southbridge"),
            ("cooler", "Active Cooler", "finned sink and blower over the SoC"), ("gpio", "GPIO Header", "2 x 20 at 2.54 mm"),
            ("ports", "Ports", "Ethernet, USB 3, USB 2, USB-C, micro HDMI"),
            ("connectors", "FPC and Card Connectors", "MIPI, PCIe, fan, microSD"))],
        "materials": {
            "pcb_green": {"base_color": [0.012, 0.15, 0.055], "metalness": 0.0, "roughness": 0.45},
            "brass": {"base_color": [0.78, 0.62, 0.30], "metalness": 1.0, "roughness": 0.3},
            "brass_gold_plated": {"base_color": [0.95, 0.76, 0.35], "metalness": 1.0, "roughness": 0.18},
            "silicon_package": {"base_color": [0.62, 0.64, 0.66], "metalness": 0.9, "roughness": 0.35},
            "aluminium_6063": {"base_color": [0.80, 0.81, 0.83], "metalness": 1.0, "roughness": 0.28},
            "plastic_black": {"base_color": [0.03, 0.03, 0.035], "metalness": 0.0, "roughness": 0.55},
            "plastic_white": {"base_color": [0.88, 0.87, 0.84], "metalness": 0.0, "roughness": 0.5},
            "steel_shell": {"base_color": [0.72, 0.73, 0.75], "metalness": 1.0, "roughness": 0.25},
        },
        "ops": ops,
    }


# ------------------------------------------------------------------ liquid-cooled gaming PC
def fan(oid: str, label: str, comp: str, at, axis: str) -> list[dict]:
    """A 120 mm fan: square frame, two struts and a 9-blade rotor, unioned into one part. Axis y, x or z."""
    t = 25.0
    parts = [
        box(f"{oid}_f", "Fan frame", comp, "plastic_black", [-60, -t / 2, -60], [60, t / 2, 60]),
        cyl(f"{oid}_b", "Fan bore", comp, "plastic_black", 58, t + 4, [0, 0, 0]),
        cut(f"{oid}_ring", "Fan frame", comp, [f"{oid}_f", f"{oid}_b"]),
        box(f"{oid}_s1", "Strut", comp, "plastic_black", [-59, -t / 2, -3], [59, -t / 2 + 3, 3]),
        box(f"{oid}_s2", "Strut", comp, "plastic_black", [-3, -t / 2, -59], [3, -t / 2 + 3, 59]),
        {"id": f"{oid}_r", "op": "rotor", "label": "Fan rotor", "component": comp, "material": "plastic_black",
         "params": {"hub_radius": 20, "tip_radius": 55, "chord": 26, "blades": 9, "pitch": 32, "twist": 18,
                    "hub_length": 19}},
    ]
    rot = {"y": [0, 0, 0], "x": [0, 0, 90], "z": [90, 0, 0]}[axis]
    parts.append({"id": oid, "op": "boolean", "label": label, "component": comp, "material": "plastic_black",
                  "inputs": [f"{oid}_ring", f"{oid}_s1", f"{oid}_s2", f"{oid}_r"],
                  "params": {"mode": "union", "rotate": rot, "translate": list(at)}})
    return parts


def fitting(oid, at, axis, h=10.0):
    """A chrome compression fitting: `at` is the centre of the face it screws into, it grows along +axis or -axis."""
    sign = -1.0 if axis.startswith("-") else 1.0
    ax = axis[-1]
    c = list(at)
    c["xyz".index(ax)] += sign * h / 2
    return cyl(oid, "Compression fitting", "fittings", "chrome", 9.5, h, c, ax)


def tube(oid, label, path):
    return {"id": oid, "op": "pipe", "label": label, "component": "coolant_loop", "material": "coolant_cyan",
            "params": {"path": [list(map(float, p)) for p in path], "radius": 7.0, "segments": 32}}


def gaming_pc() -> dict:
    X0, X1, Y0, Y1, Z0, Z1 = -115.0, 115.0, 12.0, 492.0, -225.0, 225.0   # case outside, on 12 mm feet
    P = 1.5                                                             # steel panel
    ix0, ix1 = X0 + P, 111.0                                            # inside: right panel to the glass
    ops = []
    # case
    for i, (fx, fz) in enumerate([(-95, -205), (95, -205), (-95, 205), (95, 205)]):
        ops.append(cyl(f"foot{i}", "Rubber foot", "case", "rubber", 10, Y0, [fx, Y0 / 2, fz]))
    ops.append(union("feet", "Four rubber feet", "case", [f"foot{i}" for i in range(4)]))
    ops.append(box("floor", "Bottom panel", "case", "steel_black", [X0, Y0, Z0], [X1, Y0 + P, Z1]))
    ops.append({"id": "roof", "op": "grille", "label": "Top mesh panel", "component": "case", "material": "steel_black",
                "params": {"size": [X1 - X0, P, Z1 - Z0], "hole_size": 5, "pitch": 6.5, "margin": 14,
                           "translate": [0, Y1 - P / 2, 0]}})
    ops.append(box("back", "Rear panel", "case", "steel_black", [X0, Y0 + P, Z0], [X1, Y1 - P, Z0 + P]))
    ops.append({"id": "front", "op": "grille", "label": "Front mesh panel", "component": "case", "material": "steel_black",
                "params": {"size": [X1 - X0, P, Y1 - Y0 - 2 * P], "hole_size": 5, "pitch": 6.5, "margin": 14,
                           "rotate": [90, 0, 0], "translate": [0, (Y0 + Y1) / 2, Z1 - P / 2]}})
    ops.append(box("right", "Right side panel", "case", "steel_black", [X0, Y0 + P, Z0 + P], [ix0, Y1 - P, Z1 - P]))
    ops.append(box("glass", "Tempered glass side panel", "glass", "glass_tempered", [ix1, Y0 + P, Z0 + P], [X1, Y1 - P, Z1 - P]))
    # power supply under an open-backed shroud
    sy = 100.0
    ops.append(box("shroud_o", "PSU shroud", "shroud", "steel_black", [ix0, Y0 + P, Z0 + P], [ix1, sy, Z1 - P]))
    ops.append(box("shroud_i", "PSU shroud cavity", "shroud", "steel_black", [ix0 + 1.5, Y0 - 5, Z0 - 5], [ix1 - 1.5, sy - 1.5, Z1 - P - 1.5]))
    ops.append(cut("shroud", "PSU shroud", "shroud", ["shroud_o", "shroud_i"]))
    ops.append(box("psu_o", "Power supply", "psu", "steel_black", [-100, Y0 + P, Z0 + P], [50, Y0 + P + 86, Z0 + P + 160]))
    ops.append({"id": "psu", "op": "shell", "input": "psu_o", "label": "1000 W power supply", "component": "psu",
                "material": "steel_black", "params": {"thickness": 1.0}})
    # motherboard on standoffs against the right panel
    mb_x0, mb_x1 = -103.0, -101.4
    mb = dict(y0=155.0, y1=460.0, z0=-213.0, z1=31.0)
    for i, (sy_, sz) in enumerate([(165, -203), (165, 21), (450, -203), (450, 21), (305, -203), (305, 21)]):
        ops.append(cyl(f"mbso{i}", "Motherboard standoff", "motherboard", "brass", 3, mb_x0 - ix0, [(ix0 + mb_x0) / 2, sy_, sz], "x"))
    ops.append(union("mb_standoffs", "Motherboard standoffs", "motherboard", [f"mbso{i}" for i in range(6)]))
    ops.append(box("mobo", "ATX motherboard", "motherboard", "pcb_black", [mb_x0, mb["y0"], mb["z0"]], [mb_x1, mb["y1"], mb["z1"]]))
    ops.append(box("vrm_top", "VRM heatsink (top)", "motherboard", "aluminium_dark", [mb_x1, 432, -165], [mb_x1 + 15, 450, -95]))
    ops.append(box("vrm_left", "VRM heatsink (rear)", "motherboard", "aluminium_dark", [mb_x1, 350, -185], [mb_x1 + 15, 428, -160]))
    ops.append(box("io_shroud", "Rear I/O shroud", "motherboard", "aluminium_dark", [mb_x1, 390, -213], [mb_x1 + 25, 455, -190]))
    ops.append(box("chipset", "Chipset heatsink", "motherboard", "aluminium_dark", [mb_x1, 180, -60], [mb_x1 + 10, 230, 0]))
    ops.append(box("m2", "M.2 SSD heatsink", "motherboard", "aluminium_dark", [mb_x1, 240, -150], [mb_x1 + 7, 262, -40]))
    for i in range(4):
        z0 = -83.25 + i * 7.5
        ops.append(box(f"ram{i}", "DDR5 DIMM with heat spreader", "memory", "aluminium_dark",
                       [mb_x1, 328.5, z0], [mb_x1 + 31, 461.5, z0 + 6.5]))
    ops.append(union("ram", "4 x DDR5 DIMMs", "memory", [f"ram{i}" for i in range(4)]))
    # CPU water block: copper cold plate, clear acrylic top with the coolant chamber visible
    cb = dict(y0=365.0, y1=425.0, z0=-150.0, z1=-90.0)
    ops.append(box("cpu_plate", "Copper cold plate", "cpu_block", "copper", [mb_x1, cb["y0"], cb["z0"]], [mb_x1 + 6, cb["y1"], cb["z1"]]))
    ops.append(box("cpu_top_o", "Acrylic top", "cpu_block", "acrylic_clear", [mb_x1 + 6, cb["y0"], cb["z0"]], [mb_x1 + 20, cb["y1"], cb["z1"]]))
    ops.append(box("cpu_cav", "Coolant chamber", "cpu_block", "coolant_cyan", [mb_x1 + 8, cb["y0"] + 8, cb["z0"] + 8], [mb_x1 + 17, cb["y1"] - 8, cb["z1"] - 8]))
    ops.append(cut("cpu_top", "Acrylic block top", "cpu_block", ["cpu_top_o", "cpu_cav"]))
    ops.append(box("cpu_coolant", "Coolant in the CPU block", "cpu_block", "coolant_cyan", [mb_x1 + 8, cb["y0"] + 8, cb["z0"] + 8], [mb_x1 + 17, cb["y1"] - 8, cb["z1"] - 8]))
    # GPU with a full-cover block: backplate up, block down, coolant channel open along the edge that faces the glass
    gx1 = 18.6
    g = dict(z0=-213.0, z1=67.0)
    ops.append(box("gpu_back", "GPU backplate", "gpu", "aluminium_dark", [mb_x1, 297, g["z0"]], [gx1, 300, g["z1"]]))
    ops.append(box("gpu_pcb", "Graphics card PCB", "gpu", "pcb_black", [mb_x1, 294, g["z0"]], [gx1, 297, g["z1"]]))
    ops.append(box("gpu_block_o", "Full-cover water block", "gpu", "acetal_black", [mb_x1, 272, g["z0"]], [gx1, 294, g["z1"]]))
    ops.append(box("gpu_chan", "Coolant channel", "gpu", "coolant_cyan", [-80, 278, -190], [gx1 + 1, 288, 50]))
    ops.append(cut("gpu_block", "Full-cover GPU water block", "gpu", ["gpu_block_o", "gpu_chan"]))
    ops.append(box("gpu_coolant", "Coolant in the GPU block", "gpu", "coolant_cyan", [-80, 278, -190], [gx1, 288, 50]))
    # pump and reservoir on the shroud
    rx, rz = 40.0, 150.0
    ops.append(box("pump", "D5 pump housing", "pump_res", "acetal_black", [rx - 32, sy, rz - 32], [rx + 32, sy + 40, rz + 32]))
    ops.append({"id": "res_tube", "op": "tube", "label": "Acrylic reservoir tube", "component": "pump_res",
                "material": "acrylic_clear", "params": {"height": 200, "radius": 30, "wall": 3, "segments": 96,
                                                        "translate": [rx, sy + 40 + 100, rz]}})
    ops.append(cyl("res_coolant", "Coolant in the reservoir", "pump_res", "coolant_cyan", 27, 200, [rx, sy + 40 + 100, rz], segments=96))
    ops.append(cyl("res_cap", "Reservoir top cap", "pump_res", "aluminium_dark", 32, 12, [rx, sy + 246, rz], segments=96))
    # radiator and fans under the roof, intake fans behind the front mesh, one exhaust at the back
    ry0, ry1 = Y1 - P - 27, Y1 - P
    rad = dict(z0=-195.0, z1=221.0)
    ops.append({"id": "radiator", "op": "grille", "label": "360 mm radiator", "component": "radiator",
                "material": "aluminium_dark", "params": {"size": [124, 27, rad["z1"] - rad["z0"]], "hole_size": 2.2,
                                                         "pitch": 3.2, "hole": "slot", "margin": 8,
                                                         "translate": [0, (ry0 + ry1) / 2, (rad["z0"] + rad["z1"]) / 2]}})
    for i in range(3):
        ops += fan(f"topfan{i}", "120 mm radiator fan", "fans", [0, ry0 - 12.5, rad["z0"] + 60 + i * 130], "y")
    for i, fy in enumerate([170.0, 300.0]):
        ops += fan(f"frontfan{i}", "120 mm intake fan", "fans", [0, fy, Z1 - P - 12.5], "z")
    ops += fan("rearfan", "120 mm exhaust fan", "fans", [0, 395, Z0 + P + 12.5], "z")
    # coolant loop: pump -> GPU -> CPU -> radiator -> reservoir. Each run starts and ends on a fitting's face.
    ops += [
        fitting("fit_pump", [rx - 32, 120, rz], "-x"), fitting("fit_gpu_in", [-30, 283, g["z1"]], "+z"),
        fitting("fit_gpu_out", [-91.4, 300, -120], "+y"), fitting("fit_cpu_in", [-91.4, cb["y0"], -120], "-y"),
        fitting("fit_cpu_out", [mb_x1 + 20, 410, -120], "+x"), fitting("fit_rad_in", [-30, ry0, 211], "-y"),
        fitting("fit_rad_out", [40, ry0, 211], "-y"), fitting("fit_res_in", [rx, sy + 252, rz], "+y"),
    ]
    e = 7.0                              # a pipe's rounded end reaches its radius past the path end: stop short by it
    ops += [
        tube("run_a", "Pump to GPU (hard line)", [(rx - 42 - e, 120, rz), (-30, 120, rz), (-30, 283, rz), (-30, 283, g["z1"] + 10 + e)]),
        tube("run_b", "GPU to CPU (hard line)", [(-91.4, 310 + e, -120), (-91.4, cb["y0"] - 10 - e, -120)]),
        tube("run_c", "CPU to radiator (hard line)", [(mb_x1 + 30 + e, 410, -120), (-30, 410, -120), (-30, 410, 211), (-30, ry0 - 10 - e, 211)]),
        tube("run_d", "Radiator to reservoir (hard line)", [(40, ry0 - 10 - e, 211), (40, 385, 211), (40, 385, rz), (40, sy + 262 + e, rz)]),
    ]
    return {
        "version": 1, "name": "Gaming PC, custom liquid loop", "units": "mm",
        "summary": "A glass-sided mid-tower with a hard-line custom loop: a D5 pump and reservoir push glowing cyan "
                   "coolant through a full-cover GPU block, the CPU block and a 360 mm radiator under the roof.",
        "components": [{"id": i, "label": l, "role": r} for i, l, r in (
            ("case", "Case", "steel mid-tower on rubber feet"), ("glass", "Glass Side Panel", "tempered, smoked"),
            ("shroud", "PSU Shroud", "open-backed steel cover"), ("psu", "Power Supply", "1000 W ATX"),
            ("motherboard", "Motherboard", "ATX board, VRM and chipset heatsinks"), ("memory", "Memory", "4 x DDR5"),
            ("cpu_block", "CPU Water Block", "copper cold plate, acrylic top"),
            ("gpu", "GPU and Water Block", "full-cover block, backplate"),
            ("pump_res", "Pump and Reservoir", "D5 pump, 60 mm acrylic tube"),
            ("radiator", "360 mm Radiator", "under the top mesh"), ("fans", "Fans", "six 120 mm"),
            ("fittings", "Fittings", "chrome compression"), ("coolant_loop", "Coolant Loop", "14 mm hard line, cyan"))],
        "materials": {
            "steel_black": {"base_color": [0.035, 0.037, 0.042], "metalness": 0.6, "roughness": 0.42},
            "glass_tempered": {"base_color": [0.02, 0.025, 0.03], "metalness": 0.0, "roughness": 0.06, "opacity": 0.1},
            "rubber": {"base_color": [0.02, 0.02, 0.02], "metalness": 0.0, "roughness": 0.9},
            "brass": {"base_color": [0.78, 0.62, 0.30], "metalness": 1.0, "roughness": 0.3},
            "pcb_black": {"base_color": [0.025, 0.028, 0.03], "metalness": 0.0, "roughness": 0.5},
            "aluminium_dark": {"base_color": [0.13, 0.135, 0.145], "metalness": 1.0, "roughness": 0.35},
            "copper": {"base_color": [0.95, 0.55, 0.36], "metalness": 1.0, "roughness": 0.22},
            "acrylic_clear": {"base_color": [0.85, 0.92, 0.95], "metalness": 0.0, "roughness": 0.04, "opacity": 0.28},
            "acetal_black": {"base_color": [0.025, 0.025, 0.028], "metalness": 0.0, "roughness": 0.35},
            "chrome": {"base_color": [0.86, 0.87, 0.89], "metalness": 1.0, "roughness": 0.08},
            "plastic_black": {"base_color": [0.03, 0.03, 0.035], "metalness": 0.0, "roughness": 0.55},
            "coolant_cyan": {"base_color": [0.05, 0.75, 0.95], "metalness": 0.0, "roughness": 0.08,
                             "emissive": [0.05, 0.85, 1.0], "emissive_strength": 1.6},
        },
        "ops": ops,
    }


def main() -> int:
    for name, prog in (("raspberry_pi_5", raspberry_pi()), ("gaming_pc_liquid", gaming_pc())):
        path = FIX / f"{name}.json"
        path.write_text(json.dumps(prog, indent=1))
        print(f"wrote {path} ({len(prog['ops'])} ops)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
