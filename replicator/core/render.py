"""Showcase renders: a path-traced still of the current view in Blender Cycles, on the CPU only.

The 4090 belongs to llama-swap and Berth. This runs `blender -b` with CUDA hidden and Cycles forced to the CPU
(32 threads, OIDN denoise), so nothing here opens a GPU context. A GPU path would go through a Berth lease.
Coordinates: Replicator is Y-up in mm; Blender is Z-up in metres. (x, y, z) mm -> (x, -z, y) / 1000.
"""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

BLENDER_SCRIPT = r'''
import bpy, json, math, sys
from mathutils import Vector
args = json.loads(sys.argv[sys.argv.index("--") + 1])
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
bpy.ops.import_scene.gltf(filepath=args["glb"])
imported = [o for o in sc.objects]
root = bpy.data.objects.new("replicator_root", None)
sc.collection.objects.link(root)
for o in imported:
    if o.parent is None:
        o.parent = root
root.scale = (0.001, 0.001, 0.001)
root.location = (0, 0, args["ground"] * 0.001)
for o in imported:                       # crisp CAD shading: smooth, split at edges sharper than 35 degrees
    if o.type == "MESH":
        for p in o.data.polygons:
            p.use_smooth = True
        try:
            o.data.set_sharp_from_angle(angle=math.radians(35))
        except Exception:
            pass
mats = args.get("materials", {})
part_mat = args.get("part_materials", {})
cache = {}
def principled(name, spec):
    if name in cache:
        return cache[name]
    m = bpy.data.materials.new(name); m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    c = spec.get("base_color", [0.7, 0.7, 0.72])
    b.inputs["Base Color"].default_value = (*[float(x) for x in c[:3]], 1)
    b.inputs["Metallic"].default_value = float(spec.get("metalness", 0.0))
    b.inputs["Roughness"].default_value = float(spec.get("roughness", 0.5))
    e = spec.get("emissive")
    if e and max(e) > 0:
        b.inputs["Emission Color"].default_value = (*[float(x) for x in e[:3]], 1)
        b.inputs["Emission Strength"].default_value = 6.0
    cache[name] = m
    return m
for o in imported:                       # materials straight from the BuildProgram (keeps emission)
    if o.type == "MESH":
        key = part_mat.get(o.name) or part_mat.get(o.name.split(".")[0])
        if key and key in mats:
            o.data.materials.clear()
            o.data.materials.append(principled(key, mats[key]))
R = max(args["radius"] * 0.001, 0.01)
# studio: a cyclorama floor, a big soft key, a strip rim, a cool fill
bpy.ops.mesh.primitive_plane_add(size=R * 40, location=(0, 0, 0))
floor = sc.objects[-1] if bpy.context.active_object is None else bpy.context.active_object
fm = bpy.data.materials.new("floor"); fm.use_nodes = True
b = fm.node_tree.nodes["Principled BSDF"]
b.inputs["Base Color"].default_value = (0.018, 0.019, 0.022, 1); b.inputs["Roughness"].default_value = 0.28
floor.data.materials.append(fm)
def area(name, loc, size, energy, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA"); d.shape = "RECTANGLE"; d.size = size; d.size_y = size * 0.6
    d.energy = energy; d.color = color
    o = bpy.data.objects.new(name, d); sc.collection.objects.link(o); o.location = loc
    direction = Vector((0, 0, R * 0.5)) - o.location
    o.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
area("key", (-R * 2.2, -R * 2.0, R * 3.0), R * 2.5, 420 * R * R)
area("rim", (R * 2.4, R * 2.2, R * 1.8), R * 1.2, 650 * R * R, (0.85, 0.92, 1.0))
area("fill", (R * 2.6, -R * 1.6, R * 0.8), R * 2.0, 110 * R * R, (0.8, 0.88, 1.0))
area("top", (0, 0, R * 4.0), R * 3.0, 160 * R * R)
w = bpy.data.worlds.new("w"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.013, 0.016, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0
# camera from the viewport
cam = args["camera"]
q = lambda v: Vector((v[0] * 0.001, -v[2] * 0.001, v[1] * 0.001))
cd = bpy.data.cameras.new("cam"); co = bpy.data.objects.new("cam", cd); sc.collection.objects.link(co)
sc.camera = co
co.location = q(cam["position"])
tgt = q(cam["target"])
co.rotation_euler = (tgt - co.location).to_track_quat("-Z", "Y").to_euler()
cd.sensor_fit = "VERTICAL"; cd.angle = math.radians(cam.get("fov", 38))
cd.clip_start = 0.001; cd.clip_end = R * 200
if cam.get("dof"):
    cd.dof.use_dof = True; cd.dof.focus_distance = (tgt - co.location).length; cd.dof.aperture_fstop = 2.8
sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = args.get("samples", 128)
sc.cycles.use_adaptive_sampling = True
sc.cycles.use_denoising = True
try:
    sc.cycles.denoiser = "OPENIMAGEDENOISE"
except Exception:
    pass
sc.render.threads_mode = "FIXED"; sc.render.threads = args.get("threads", 28)
sc.render.resolution_x = cam["width"]; sc.render.resolution_y = cam["height"]; sc.render.resolution_percentage = 100
try:
    sc.view_settings.view_transform = "AgX"; sc.view_settings.look = "AgX - Medium High Contrast"
except Exception:
    sc.view_settings.view_transform = "Filmic"
sc.render.film_transparent = False
sc.render.filepath = args["out"]
bpy.ops.render.render(write_still=True)
print("REPLICATOR_RENDER_OK", args["out"])
'''


def cycles_still(glb: Path, out: Path, camera: dict, materials: dict | None = None, ground: float = 0.0,
                 samples: int = 128, log=print, part_materials: dict | None = None) -> Path:
    camera = dict(camera)
    w, h = int(camera.get("width", 1600)), int(camera.get("height", 900))
    scale = min(1.0, 1920 / max(w, 1))
    camera["width"], camera["height"] = int(w * scale) // 2 * 2, int(h * scale) // 2 * 2
    radius = float(camera.get("radius", 300))
    args = {"glb": str(glb), "out": str(out), "camera": camera, "ground": ground, "radius": radius,
            "samples": samples, "threads": max(4, (os.cpu_count() or 8) - 4),
            "materials": materials or {}, "part_materials": part_materials or {}}
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", __EGL_VENDOR_LIBRARY_FILENAMES=
               "/usr/share/glvnd/egl_vendor.d/50_mesa.json", __GLX_VENDOR_LIBRARY_NAME="mesa")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(BLENDER_SCRIPT)
        script = f.name
    try:
        p = subprocess.run(["blender", "-b", "--factory-startup", "--python", script, "--", json.dumps(args)],
                           capture_output=True, text=True, env=env, timeout=1800)
    finally:
        os.unlink(script)
    if "REPLICATOR_RENDER_OK" not in p.stdout or not out.exists():
        tail = "\n".join((p.stdout + p.stderr).splitlines()[-15:])
        raise RuntimeError(f"Blender render failed:\n{tail}")
    return out
