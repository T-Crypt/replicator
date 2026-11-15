"""Export a build to GLB, OBJ, STL, 3MF (trimesh) or STEP (faceted B-rep, core/step.py). STL and 3MF are for printers: they refuse anything that is not
watertight (prints must not fail) and are written Z-up, the printer convention, so importing them back is lossless. With a printer given, print formats
are also refused when the build overflows its bed (core/fit.py), naming the overflow per axis; it is never clipped."""
from __future__ import annotations

from pathlib import Path

import trimesh

from . import fit
from .evaluate import Shape
from .printers import Printer

PRINT_FORMATS = ("stl", "3mf")
CAD_FORMATS = ("step", "stp")
FORMATS = ("glb", "gltf", "obj", *PRINT_FORMATS, *CAD_FORMATS)
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


def _gate_bed(shapes: list[Shape], units: str, printer: Printer) -> None:
    """Refuse a build that overflows the printer's bed, naming every axis and how much, and the replica
    scale that would fit it. The as-built factor, because the file stands as built and cannot be rotated."""
    r = fit.check(shapes, units, printer)
    if r.fits:
        return
    over = ", ".join(f"{ax} by {v:.1f} mm" for ax, v in zip(fit.AXES, r.overflow) if v > 0)
    s = fit.scale_to_fit(shapes, units, printer, allow_rotate=False).scale
    raise ValueError(f"{printer.name} ({printer.id}): the build is {r.size[0]:.1f} x {r.size[1]:.1f} x "
                     f"{r.size[2]:.1f} mm but only {r.usable[0]:.1f} x {r.usable[1]:.1f} x {r.usable[2]:.1f} mm "
                     f"is usable; it overflows {over}. A {s:.3f}x replica would fit")


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


def export(shapes: list[Shape], materials: dict, path: str | Path, name: str = "", units: str = "mm",
           printer: Printer | None = None) -> Path:
    path = Path(path)
    fmt = path.suffix.lower().lstrip(".")
    if fmt not in FORMATS:
        raise ValueError(f"unsupported format {fmt or path.name}; use one of {', '.join(FORMATS)}")
    if not shapes:
        raise ValueError("nothing to export: the build has no visible parts")
    if fmt in CAD_FORMATS:
        from . import step
        step.write(shapes, path, name=name or path.stem, units=units)
    elif fmt in PRINT_FORMATS:
        if printer is not None:
            _gate_bed(shapes, units, printer)
        _print_file(shapes, materials, fmt, path)
    elif fmt == "obj":
        to_scene(shapes, materials).export(path, mtl_name=f"{path.stem}.mtl")
    else:
        to_scene(shapes, materials).export(path)
    return path
