"""Bring any 3D file into Replicator: a route per format, each ending in a file `reverse.load_pieces` can read.

Print galleries (Printables, Thingiverse, MakerWorld) ship STL, 3MF and ZIP bundles; CAD stores ship STEP and IGES;
asset stores ship FBX, glTF, USD and .blend. trimesh reads the mesh formats directly, cascadio (OpenCASCADE)
tessellates CAD, and headless Blender on the CPU converts the rest to GLB. Archives are untrusted downloads: they are
unpacked into their own empty folder with size, count and path checks, and only model files inside are used.
"""
from __future__ import annotations

import json
import os
import subprocess
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

import trimesh

MAX_UNPACKED = 2 * 1024 ** 3
MAX_MEMBERS = 5000


@dataclass(frozen=True)
class Route:
    kind: str            # "mesh" | "cad" | "blender" | "archive"
    label: str
    z_up: bool = False   # printer formats are Z-up by convention; glTF (and cascadio's GLB) and Replicator are Y-up


ROUTES: dict[str, Route] = {
    ".glb": Route("mesh", "glTF binary"), ".gltf": Route("mesh", "glTF"), ".obj": Route("mesh", "Wavefront OBJ"),
    ".ply": Route("mesh", "PLY"), ".off": Route("mesh", "OFF"), ".dae": Route("mesh", "Collada"),
    ".stl": Route("mesh", "STL (3D printing)", z_up=True), ".3mf": Route("mesh", "3MF (3D printing)", z_up=True),
    ".3dxml": Route("mesh", "3DXML (CATIA)"),
    ".step": Route("cad", "STEP (CAD)"), ".stp": Route("cad", "STEP (CAD)"),
    ".iges": Route("cad", "IGES (CAD)"), ".igs": Route("cad", "IGES (CAD)"),
    ".fbx": Route("blender", "FBX"), ".usd": Route("blender", "USD"), ".usda": Route("blender", "USD"),
    ".usdc": Route("blender", "USD"), ".usdz": Route("blender", "USDZ"), ".abc": Route("blender", "Alembic"),
    ".blend": Route("blender", "Blender scene"),
    ".zip": Route("archive", "ZIP bundle"), ".tar": Route("archive", "TAR bundle"),
    ".tgz": Route("archive", "TAR bundle"), ".gz": Route("archive", "TAR bundle"),
}
PREFERENCE = [".3mf", ".step", ".stp", ".glb", ".gltf", ".fbx", ".obj", ".stl", ".ply", ".blend", ".usdz", ".usd",
              ".dae", ".iges", ".igs", ".off", ".abc", ".usda", ".usdc", ".3dxml"]


def patterns() -> str:
    """For file dialogs: '*.glb *.stl ...'."""
    return " ".join(f"*{e}" for e in ROUTES)


def route(path: Path) -> Route:
    r = ROUTES.get(path.suffix.lower())
    if r is None:
        raise ValueError(f"{path.suffix or path.name} is not a 3D format Replicator reads; supported: {patterns()}")
    return r


BLENDER_EXPORT = r'''
import bpy, json, sys
a = json.loads(sys.argv[sys.argv.index("--") + 1])
ext = a["src"].lower().rsplit(".", 1)[-1]
if ext != "blend":
    bpy.ops.wm.read_factory_settings(use_empty=True)
    if ext == "fbx":
        bpy.ops.import_scene.fbx(filepath=a["src"])
    elif ext == "abc":
        bpy.ops.wm.alembic_import(filepath=a["src"])
    else:
        bpy.ops.wm.usd_import(filepath=a["src"])
for o in bpy.context.scene.objects:
    o.select_set(o.type in {"MESH", "CURVE", "SURFACE", "META", "FONT"})
bpy.ops.export_scene.gltf(filepath=a["dst"], export_format="GLB", use_selection=True, export_apply=True,
                          export_yup=True, export_animations=False)
'''


def _blender(src: Path, dst: Path) -> Path:
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", BLENDERMCP_NO_UPDATE_CHECK="1")
    cmd = ["blender", "-b"] + ([str(src)] if src.suffix.lower() == ".blend" else ["--factory-startup"])
    cmd += ["--python-expr", BLENDER_EXPORT, "--", json.dumps({"src": str(src), "dst": str(dst)})]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=600)
    if not dst.exists():
        tail = (r.stderr or r.stdout).strip().splitlines()[-3:]
        raise RuntimeError(f"Blender could not convert {src.name}: {' / '.join(tail) or 'no output'}")
    return dst


def _cad(src: Path, dst: Path) -> Path:
    import cascadio
    kind = cascadio.FileType.IGES if src.suffix.lower() in (".iges", ".igs") else cascadio.FileType.STEP
    dst.write_bytes(cascadio.to_glb_bytes(src.read_bytes(), file_type=kind, tol_linear=0.05, tol_angular=0.3,
                                          include_materials=True))
    if dst.stat().st_size == 0:
        raise RuntimeError(f"{src.name}: OpenCASCADE produced no geometry")
    return dst


def _safe_members(names: list[tuple[str, int]], dest: Path) -> None:
    if len(names) > MAX_MEMBERS:
        raise ValueError(f"archive has {len(names)} entries (limit {MAX_MEMBERS})")
    if sum(size for _, size in names) > MAX_UNPACKED:
        raise ValueError("archive unpacks to more than 2 GB")
    root = dest.resolve()
    for name, _ in names:
        target = (dest / name).resolve()
        if root != target and root not in target.parents:
            raise ValueError(f"archive entry {name!r} would land outside its folder")


def unpack(src: Path, dest: Path) -> list[Path]:
    """Extract an archive into the empty folder `dest`; return the model files inside, best format first."""
    dest.mkdir(parents=True, exist_ok=False)
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            infos = [i for i in z.infolist() if not i.is_dir()]
            _safe_members([(i.filename, i.file_size) for i in infos], dest)
            z.extractall(dest, members=infos)
    elif tarfile.is_tarfile(src):
        with tarfile.open(src) as t:
            infos = [m for m in t.getmembers() if m.isfile()]
            _safe_members([(m.name, m.size) for m in infos], dest)
            t.extractall(dest, members=infos, filter="data")
    else:
        raise ValueError(f"{src.name} is not a ZIP or TAR archive")
    models = [p for p in dest.rglob("*") if p.is_file() and p.suffix.lower() in ROUTES
              and ROUTES[p.suffix.lower()].kind != "archive" and not p.name.startswith(".")]
    if not models:
        raise ValueError(f"{src.name} holds no 3D model files")
    rank = {e: i for i, e in enumerate(PREFERENCE)}
    best = min(rank.get(p.suffix.lower(), 99) for p in models)
    return sorted(p for p in models if rank.get(p.suffix.lower(), 99) == best)


def _scene(path: Path, z_up: bool) -> trimesh.Scene:
    scene = trimesh.load(str(path), force="scene")
    if z_up:
        scene.apply_transform(trimesh.transformations.rotation_matrix(-1.5707963267948966, [1, 0, 0]))
    return scene


def prepare(src: Path, work: Path, log=print) -> tuple[Path, str]:
    """(a GLB in Replicator's Y-up frame, a one-line description). `work` is an empty folder this import owns."""
    work.mkdir(parents=True, exist_ok=True)
    r = route(src)
    if r.kind == "archive":
        models = unpack(src, work / "unpacked")
        log(f"import: {src.name} holds {len(models)} {models[0].suffix} file(s)")
        merged = trimesh.Scene()
        for m in models[:200]:
            glb, _ = prepare(m, work / f"part-{m.stem}", log)
            merged.add_geometry(trimesh.load(str(glb), force="scene").to_geometry(), node_name=m.stem)
        out = work / f"{src.stem}.glb"
        merged.export(out)
        return out, f"{r.label}: {len(models)} {route(models[0]).label} file(s)"
    if r.kind == "cad":
        log(f"import: tessellating {src.name} with OpenCASCADE")
        return _cad(src, work / f"{src.stem}.glb"), r.label
    if r.kind == "blender":
        log(f"import: converting {src.name} with Blender (CPU)")
        return _blender(src, work / f"{src.stem}.glb"), r.label
    out = work / f"{src.stem}.glb"
    _scene(src, r.z_up).export(out)
    return out, r.label
