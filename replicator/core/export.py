"""Export a build to GLB, OBJ or STL with trimesh. STL refuses anything that is not watertight (prints must not fail)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

from .evaluate import Shape


def _material(spec: dict | None) -> trimesh.visual.material.PBRMaterial:
    spec = spec or {}
    c = list(spec.get("base_color", [0.7, 0.7, 0.72]))
    return trimesh.visual.material.PBRMaterial(
        baseColorFactor=[*c[:3], 1.0], metallicFactor=float(spec.get("metalness", 0.0)),
        roughnessFactor=float(spec.get("roughness", 0.5)))


def to_scene(shapes: list[Shape], materials: dict) -> trimesh.Scene:
    scene = trimesh.Scene()
    for s in shapes:
        v, f = s.arrays()
        mesh = trimesh.Trimesh(v, f, process=False)
        mesh.visual = trimesh.visual.TextureVisuals(material=_material(materials.get(s.material)))
        scene.add_geometry(mesh, node_name=s.id, geom_name=s.part)
    return scene


def export(shapes: list[Shape], materials: dict, path: str | Path) -> Path:
    path = Path(path)
    fmt = path.suffix.lower().lstrip(".")
    if fmt == "stl":
        bad = [s.id for s in shapes if s.manifold.status().name != "NoError" or s.manifold.genus() < 0]
        if bad:
            raise ValueError(f"not watertight: {bad}")
        merged = trimesh.util.concatenate([trimesh.Trimesh(*s.arrays(), process=False) for s in shapes])
        if not merged.is_watertight:
            raise ValueError("merged mesh is not watertight")
        merged.export(path)
    elif fmt in ("glb", "gltf", "obj"):
        to_scene(shapes, materials).export(path)
    else:
        raise ValueError(f"unsupported format {fmt}")
    return path
