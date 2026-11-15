"""Export a build to GLB, OBJ, STL or 3MF with trimesh. STL and 3MF are for printers: they refuse anything that is not
watertight (prints must not fail) and are written Z-up, the printer convention, so importing them back is lossless."""
from __future__ import annotations

from pathlib import Path

import trimesh

from .evaluate import Shape

PRINT_FORMATS = ("stl", "3mf")
FORMATS = ("glb", "gltf", "obj", *PRINT_FORMATS)
Y_TO_Z_UP = trimesh.transformations.rotation_matrix(1.5707963267948966, [1, 0, 0])


def _material(spec: dict | None, name: str) -> trimesh.visual.material.PBRMaterial:
    spec = spec or {}
    c = list(spec.get("base_color", [0.7, 0.7, 0.72]))
    a = min(max(float(spec.get("opacity", 1.0)), 0.0), 1.0)      # glass and clear panels: glTF alpha blend
    return trimesh.visual.material.PBRMaterial(
        name=name, baseColorFactor=[*c[:3], a], metallicFactor=float(spec.get("metalness", 0.0)),
        roughnessFactor=float(spec.get("roughness", 0.5)), alphaMode="BLEND" if a < 1.0 else None)


def to_scene(shapes: list[Shape], materials: dict) -> trimesh.Scene:
    scene = trimesh.Scene()
    made: dict[str, trimesh.visual.material.PBRMaterial] = {}
    for s in shapes:
        v, f = s.arrays()
        mesh = trimesh.Trimesh(v, f, process=False)
        name = s.material or "default"
        if name not in made:
            made[name] = _material(materials.get(s.material), name)
        mesh.visual = trimesh.visual.TextureVisuals(material=made[name])
        scene.add_geometry(mesh, node_name=s.id, geom_name=s.part)
    return scene


def _printable(shapes: list[Shape], fmt: str) -> None:
    bad = [s.id for s in shapes if s.manifold.status().name != "NoError"]
    if bad:
        raise ValueError(f"{fmt.upper()} needs closed solids; these parts are open surfaces or broken: {bad}. "
                         "Imported surfaces are shown and moved but cannot be printed; export GLB instead")


def _print_file(shapes: list[Shape], materials: dict, fmt: str, path: Path) -> None:
    _printable(shapes, fmt)
    scene = to_scene(shapes, materials)
    scene.apply_transform(Y_TO_Z_UP)
    if fmt == "3mf":                       # one object per part, named, so a slicer can colour and arrange them
        scene.export(path)
        return
    merged = scene.to_geometry()
    if not merged.is_watertight:
        raise ValueError("parts touch along an edge or face so the combined mesh is not watertight; "
                         "union them with a boolean, or separate them")
    merged.export(path)


def export(shapes: list[Shape], materials: dict, path: str | Path) -> Path:
    path = Path(path)
    fmt = path.suffix.lower().lstrip(".")
    if fmt not in FORMATS:
        raise ValueError(f"unsupported format {fmt or path.name}; use one of {', '.join(FORMATS)}")
    if not shapes:
        raise ValueError("nothing to export: the build has no visible parts")
    if fmt in PRINT_FORMATS:
        _print_file(shapes, materials, fmt, path)
    elif fmt == "obj":
        to_scene(shapes, materials).export(path, mtl_name=f"{path.stem}.mtl")
    else:
        to_scene(shapes, materials).export(path)
    return path
