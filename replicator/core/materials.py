"""The material library: named PBR presets a program can use. A preset is copied into the program's `materials`
the first time it is applied, so a saved program never depends on this file.

Values are metal/rough PBR in linear base colour, picked to read well under the workshop HDRI and in Cycles.
"""
from __future__ import annotations

# id -> (label, group, definition)
PRESETS: dict[str, tuple[str, str, dict]] = {
    "steel": ("Steel", "Metal", {"base_color": [0.62, 0.64, 0.68], "metalness": 1.0, "roughness": 0.3}),
    "brushed_aluminium": ("Brushed aluminium", "Metal", {"base_color": [0.80, 0.81, 0.83], "metalness": 1.0, "roughness": 0.45}),
    "chrome": ("Chrome", "Metal", {"base_color": [0.90, 0.91, 0.93], "metalness": 1.0, "roughness": 0.06}),
    "titanium": ("Titanium", "Metal", {"base_color": [0.54, 0.52, 0.50], "metalness": 1.0, "roughness": 0.38}),
    "gunmetal": ("Gunmetal", "Metal", {"base_color": [0.20, 0.22, 0.25], "metalness": 1.0, "roughness": 0.42}),
    "cast_iron": ("Cast iron", "Metal", {"base_color": [0.13, 0.13, 0.14], "metalness": 0.9, "roughness": 0.72}),
    "copper": ("Copper", "Metal", {"base_color": [0.95, 0.52, 0.34], "metalness": 1.0, "roughness": 0.25}),
    "brass": ("Brass", "Metal", {"base_color": [0.89, 0.72, 0.36], "metalness": 1.0, "roughness": 0.3}),
    "gold": ("Gold", "Metal", {"base_color": [1.0, 0.77, 0.34], "metalness": 1.0, "roughness": 0.18}),
    "anodised_blue": ("Anodised blue", "Metal", {"base_color": [0.10, 0.32, 0.78], "metalness": 1.0, "roughness": 0.32}),
    "anodised_red": ("Anodised red", "Metal", {"base_color": [0.72, 0.08, 0.10], "metalness": 1.0, "roughness": 0.32}),
    "titanium_ti6al4v": ("Ti-6Al-4V, machined", "Aerospace", {"base_color": [0.56, 0.54, 0.51], "metalness": 1.0, "roughness": 0.3}),
    "titanium_blasted": ("Titanium, bead-blasted", "Aerospace", {"base_color": [0.50, 0.49, 0.47], "metalness": 1.0, "roughness": 0.62}),
    "titanium_heat_tint": ("Titanium, heat-tinted", "Aerospace", {"base_color": [0.33, 0.30, 0.56], "metalness": 1.0, "roughness": 0.28}),
    "inconel_718": ("Inconel 718", "Aerospace", {"base_color": [0.48, 0.46, 0.43], "metalness": 1.0, "roughness": 0.4}),
    "inconel_heat": ("Inconel, heat-straw", "Aerospace", {"base_color": [0.36, 0.24, 0.13], "metalness": 1.0, "roughness": 0.46}),
    "aluminium_7075_black": ("7075-T6, black anodised", "Aerospace", {"base_color": [0.03, 0.03, 0.035], "metalness": 1.0, "roughness": 0.34}),
    "aluminium_7075": ("7075-T6, clear anodised", "Aerospace", {"base_color": [0.76, 0.77, 0.79], "metalness": 1.0, "roughness": 0.38}),
    "steel_maraging": ("Maraging steel", "Aerospace", {"base_color": [0.40, 0.41, 0.43], "metalness": 1.0, "roughness": 0.3}),
    "tungsten": ("Tungsten", "Aerospace", {"base_color": [0.45, 0.45, 0.47], "metalness": 1.0, "roughness": 0.34}),
    "carbon_cfrp_twill": ("CFRP twill, clear-coated", "Aerospace", {"base_color": [0.03, 0.032, 0.036], "metalness": 0.25, "roughness": 0.16}),
    "peek": ("PEEK", "Aerospace", {"base_color": [0.62, 0.52, 0.38], "metalness": 0.0, "roughness": 0.4}),
    "kevlar": ("Aramid (Kevlar)", "Aerospace", {"base_color": [0.78, 0.60, 0.14], "metalness": 0.0, "roughness": 0.6}),
    "tps_tile": ("Thermal tile (TPS)", "Aerospace", {"base_color": [0.035, 0.035, 0.04], "metalness": 0.0, "roughness": 0.88}),
    "steel_cerakote_black": ("Cerakote, graphite black", "Aerospace", {"base_color": [0.05, 0.05, 0.055], "metalness": 0.1, "roughness": 0.58}),
    "steel_cerakote_fde": ("Cerakote, flat dark earth", "Aerospace", {"base_color": [0.42, 0.35, 0.25], "metalness": 0.05, "roughness": 0.6}),
    "abs_white": ("ABS white", "Polymer", {"base_color": [0.88, 0.88, 0.86], "metalness": 0.0, "roughness": 0.42}),
    "abs_black": ("ABS black", "Polymer", {"base_color": [0.035, 0.035, 0.04], "metalness": 0.0, "roughness": 0.45}),
    "rubber": ("Rubber", "Polymer", {"base_color": [0.025, 0.025, 0.028], "metalness": 0.0, "roughness": 0.9}),
    "carbon_fibre": ("Carbon fibre", "Polymer", {"base_color": [0.045, 0.048, 0.055], "metalness": 0.35, "roughness": 0.28}),
    "ceramic": ("Ceramic", "Polymer", {"base_color": [0.93, 0.92, 0.89], "metalness": 0.0, "roughness": 0.12}),
    "clay": ("Clay", "Polymer", {"base_color": [0.78, 0.76, 0.72], "metalness": 0.0, "roughness": 0.62}),
    "paint_orange": ("Safety orange", "Paint", {"base_color": [1.0, 0.36, 0.03], "metalness": 0.0, "roughness": 0.3}),
    "paint_red": ("Signal red", "Paint", {"base_color": [0.78, 0.04, 0.05], "metalness": 0.0, "roughness": 0.22}),
    "paint_yellow": ("Machine yellow", "Paint", {"base_color": [0.96, 0.72, 0.04], "metalness": 0.0, "roughness": 0.3}),
    "paint_green": ("Racing green", "Paint", {"base_color": [0.02, 0.22, 0.12], "metalness": 0.0, "roughness": 0.2}),
    "paint_blue": ("Cobalt blue", "Paint", {"base_color": [0.03, 0.16, 0.62], "metalness": 0.0, "roughness": 0.2}),
    "paint_white": ("Gloss white", "Paint", {"base_color": [0.95, 0.95, 0.95], "metalness": 0.0, "roughness": 0.16}),
    "glow_holo": ("Holo glow", "Glow", {"base_color": [0.02, 0.10, 0.14], "metalness": 0.0, "roughness": 0.4, "emissive": [0.2, 0.85, 1.0]}),
    "glow_ember": ("Ember glow", "Glow", {"base_color": [0.14, 0.04, 0.01], "metalness": 0.0, "roughness": 0.4, "emissive": [1.0, 0.42, 0.08]}),
    "glow_plasma": ("Plasma glow", "Glow", {"base_color": [0.08, 0.03, 0.14], "metalness": 0.0, "roughness": 0.4, "emissive": [0.72, 0.38, 1.0]}),
    "glow_reactor": ("Reactor green", "Glow", {"base_color": [0.02, 0.12, 0.05], "metalness": 0.0, "roughness": 0.4, "emissive": [0.3, 1.0, 0.45]}),
}


def rows() -> list[dict]:
    """The library as plain rows for the UI."""
    return [{"id": k, "label": label, "group": group, **_view(d)} for k, (label, group, d) in PRESETS.items()]


def program_rows(program: dict | None) -> list[dict]:
    """The materials a program already defines, in the same row shape."""
    mats = (program or {}).get("materials", {})
    return [{"id": k, "label": PRESETS[k][0] if k in PRESETS else k.replace("_", " "), "group": "In this build",
             **_view(d)} for k, d in mats.items() if isinstance(d, dict)]


def _view(d: dict) -> dict:
    c = [min(max(float(x), 0.0), 1.0) for x in (d.get("base_color") or [0.72, 0.73, 0.76])[:3]]
    e = [min(max(float(x), 0.0), 1.0) for x in (d.get("emissive") or [0, 0, 0])[:3]]
    return {"color": _hex(c), "emissive": _hex(e), "metalness": float(d.get("metalness", 0.0)),
            "roughness": float(d.get("roughness", 0.5))}


def _hex(c: list[float]) -> str:
    # linear -> sRGB for a faithful 2D swatch
    return "#" + "".join(f"{round(255 * (x ** (1 / 2.2))):02x}" for x in c)


def apply(program: dict, op_ids: list[str], preset: str) -> dict:
    """Give `op_ids` the material `preset` (a library id or a material the program already has). In place."""
    mats = program.setdefault("materials", {})
    if preset in PRESETS:
        mats[preset] = dict(PRESETS[preset][2])
    elif preset not in mats:
        raise ValueError(f"unknown material {preset!r}")
    hit = 0
    for op in program["ops"]:
        if op["id"] in op_ids:
            op["material"] = preset
            hit += 1
    if not hit:
        raise ValueError("nothing selected to paint")
    return program


def swap(program: dict, old: str, preset: str) -> dict:
    """Every part made of `old` becomes `preset` (a whole-build material variant). In place."""
    ids = [op["id"] for op in program["ops"] if op.get("material") == old]
    if not ids:
        raise ValueError(f"no part uses {old!r}")
    apply(program, ids, preset)
    if old != preset and not any(op.get("material") == old for op in program["ops"]):
        program["materials"].pop(old, None)
    return program
