"""Replicator <-> Blender through the mcp-for-blender add-on (vendored, pinned; see vendor/mcp-for-blender/PIN.md).

Open in Blender: start the Blender GUI (CUDA hidden, update check off), import the current build
with its BuildProgram materials, and start the add-on's socket server on localhost:9876. From there any local agent
can drive Blender through the MCP server (`DISABLE_TELEMETRY=true`), or Replicator itself talks to the socket.
Pull from Blender: export the live Blender scene to GLB over that socket and reverse-engineer it back into a
program, so whatever was changed in Blender (by hand or by an agent) can be dissected, timelined and showcased.

Protocol (the add-on's): one JSON object per request {"type": cmd, "params": {...}} -> {"status", "result"|"message"}.
"""
from __future__ import annotations

import json
import os
import socket
import subprocess
import tempfile
import time
from pathlib import Path

HOST, PORT = "127.0.0.1", 9876

OPEN_SCRIPT = r'''
import bpy, json, sys
args = json.loads(sys.argv[sys.argv.index("--") + 1])
def setup():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.ops.import_scene.gltf(filepath=args["glb"])
    mats, parts = args["materials"], args["parts"]
    made, cols = {}, {}
    for o in list(bpy.context.scene.objects):
        info = parts.get(o.name) or parts.get(o.name.split(".")[0])
        if o.type != "MESH" or info is None:
            continue
        o["replicator_id"], o["replicator_component"] = info["id"], info["component"]
        col = cols.get(info["component"])
        if col is None:
            col = cols[info["component"]] = bpy.data.collections.new(info["component_label"])
            bpy.context.scene.collection.children.link(col)
        for c in list(o.users_collection):
            c.objects.unlink(o)
        col.objects.link(o)
        o.name = info["label"]
        key = info["material"]
        if key not in mats:
            continue
        if key not in made:
            m = bpy.data.materials.new(key); m.use_nodes = True
            b = m.node_tree.nodes["Principled BSDF"]; s = mats[key]
            b.inputs["Base Color"].default_value = (*s.get("base_color", [0.7, 0.7, 0.72])[:3], 1)
            b.inputs["Metallic"].default_value = s.get("metalness", 0.0)
            b.inputs["Roughness"].default_value = s.get("roughness", 0.5)
            if s.get("emissive") and max(s["emissive"]) > 0:
                b.inputs["Emission Color"].default_value = (*s["emissive"][:3], 1)
                b.inputs["Emission Strength"].default_value = 6.0
            made[key] = m
        o.data.materials.clear(); o.data.materials.append(made[key])
        for p in o.data.polygons:
            p.use_smooth = True
    root = bpy.data.objects.new("Replicator build (mm)", None)
    bpy.context.scene.collection.objects.link(root)
    for o in bpy.context.scene.objects:
        if o.parent is None and o is not root:
            o.parent = root
    root.scale = (0.001, 0.001, 0.001)
    try:
        bpy.ops.blendermcp.start_server()
    except Exception as e:
        print("REPLICATOR: could not start the MCP socket:", e)
    for area in bpy.context.screen.areas if bpy.context.screen else []:
        if area.type == "VIEW_3D":
            with bpy.context.temp_override(area=area, region=area.regions[-1]):
                bpy.ops.view3d.view_all()
    return None
bpy.app.timers.register(setup, first_interval=1.0)
'''


def _env() -> dict:
    """Blender's GUI follows the window's GPU policy (replicator.gpu): on the iGPU when the app is pinned there."""
    from .. import gpu
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="", BLENDERMCP_NO_UPDATE_CHECK="1", DISABLE_TELEMETRY="true")
    if gpu.should_pin():
        env.update(__EGL_VENDOR_LIBRARY_FILENAMES=gpu.MESA_EGL, __GLX_VENDOR_LIBRARY_NAME="mesa")
    return env


def is_up(timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((HOST, PORT), timeout=timeout):
            return True
    except OSError:
        return False


def send(cmd: str, params: dict | None = None, timeout: float = 120) -> dict:
    with socket.create_connection((HOST, PORT), timeout=timeout) as s:
        s.sendall(json.dumps({"type": cmd, "params": params or {}}).encode())
        buf = b""
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
            try:
                return json.loads(buf.decode())
            except json.JSONDecodeError:
                continue
    raise ConnectionError("Blender closed the connection without a reply")


def open_in_blender(glb: Path, materials: dict, parts: dict) -> subprocess.Popen:
    """`parts`: shape id -> {id, label, component, component_label, material}; objects land in one collection per
    component, named by label and tagged with their replicator id."""
    args = {"glb": str(glb), "materials": materials, "parts": parts}
    fd, script = tempfile.mkstemp(suffix=".py", prefix="replicator_open_")
    with os.fdopen(fd, "w") as f:
        f.write(OPEN_SCRIPT)
    return subprocess.Popen(["blender", "--python", script, "--", json.dumps(args)], env=_env(),
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


ROOT_NAME = "Replicator build (mm)"


def wait_up(seconds: float = 40) -> bool:
    """True once the socket answers AND our build is in the scene (the add-on may auto-start its server before
    the import has run, and an early pull would grab Blender's default cube)."""
    end = time.time() + seconds
    while time.time() < end:
        if is_up():
            try:
                info = send("get_scene_info", timeout=10)
                names = json.dumps(info.get("result", {}))
                if ROOT_NAME in names:
                    return True
            except (OSError, ValueError, ConnectionError):
                pass
        time.sleep(0.5)
    return False


def pull_scene(dest: Path) -> Path:
    """Export the live Blender scene (meshes only) to a Y-up GLB in millimetres via the add-on's execute_code."""
    code = f'''
import bpy
for o in bpy.context.scene.objects:
    o.select_set(o.type == "MESH")
root = bpy.data.objects.get("Replicator build (mm)")
saved = tuple(root.scale) if root else None
if root: root.scale = (1, 1, 1)
bpy.ops.export_scene.gltf(filepath={str(dest)!r}, export_format="GLB", use_selection=True, export_yup=True,
                          export_apply=True)
if root: root.scale = saved
print("exported")
'''
    r = send("execute_code", {"code": code}, timeout=300)
    if r.get("status") != "success" or not dest.exists():
        raise RuntimeError(f"Blender export failed: {r.get('message') or r}")
    return dest
