"""ComfyUI under a Berth lease: upload images, run API-format workflows, fetch outputs.

The card hand-off is not reimplemented here. `bridge.ensure_up()` from the homelab ComfyUI tooling
(~/homelab/scripts/comfy/bridge.py) is the one sanctioned way to get ComfyUI holding the card: it stops Strata,
wakes a parked ComfyUI or switches the card to it through the Berth gateway, and opens a batch so the card stays
put between our two jobs. `release()` ends that batch so a waiting chat gets the card straight back.
Override the bridge location with REPLICATOR_COMFY_BRIDGE.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

BRIDGE_DIR = Path(os.environ.get("REPLICATOR_COMFY_BRIDGE", Path.home() / "homelab" / "scripts" / "comfy"))
COMFY = os.environ.get("COMFY_LOCAL_URL", "http://127.0.0.1:8188").rstrip("/")

MODEL_SINGLE = "hunyuan_3d_v2.1.safetensors"
MODEL_MULTI = "hunyuan3d-dit-v2-mv_fp16.safetensors"
BG_MODEL = "birefnet.safetensors"


class ComfyError(RuntimeError):
    pass


def _bridge():
    if str(BRIDGE_DIR) not in sys.path:
        sys.path.insert(0, str(BRIDGE_DIR))
    try:
        import bridge  # noqa: PLC0415  (homelab/scripts/comfy/bridge.py)
    except ImportError as e:
        raise ComfyError(f"ComfyUI bridge not found in {BRIDGE_DIR} ({e}); set REPLICATOR_COMFY_BRIDGE") from e
    return bridge


def acquire(log=print) -> None:
    """Block until ComfyUI holds the card (Berth lease). Raises ComfyError when it cannot."""
    os.environ.setdefault("COMFY_BATCH", "120")  # keep the card between the mask job and the mesh job
    os.environ.setdefault("GEN_CLIENT", "replicator")
    log("image3d: asking Berth for the card (ComfyUI)")
    b = _bridge()
    try:
        b.ensure_up()
    except SystemExit as e:  # bridge exits with wake instructions when it cannot start ComfyUI
        raise ComfyError(f"ComfyUI could not get the card ({e})") from e
    log("image3d: ComfyUI holds the card")


def release() -> None:
    try:
        _bridge().end_batch()
    except ComfyError:
        pass


def _json(path: str, body: dict | None = None, timeout: float = 60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(COMFY + path, data=data, headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        raise ComfyError(f"ComfyUI {path}: HTTP {e.code} {e.read()[:600].decode(errors='replace')}") from e


def upload(path: Path, subfolder: str = "replicator") -> str:
    """POST /upload/image; returns the name LoadImage wants ("replicator/x.png")."""
    boundary = uuid.uuid4().hex
    body = b"".join([
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"subfolder\"\r\n\r\n{subfolder}\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"overwrite\"\r\n\r\ntrue\r\n".encode(),
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{path.name}\"\r\n"
        f"Content-Type: image/png\r\n\r\n".encode(), path.read_bytes(), f"\r\n--{boundary}--\r\n".encode()])
    req = urllib.request.Request(COMFY + "/upload/image", data=body,
                                 headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        res = json.load(r)
    return f"{res['subfolder']}/{res['name']}" if res.get("subfolder") else res["name"]


def run(workflow: dict, log=print, timeout: float = 900) -> dict:
    """Queue an API-format workflow and wait for it; returns the history entry's outputs."""
    cid = "replicator-" + uuid.uuid4().hex[:8]
    res = _json("/prompt", {"prompt": workflow, "client_id": cid})
    if res.get("node_errors"):
        raise ComfyError(f"workflow rejected: {json.dumps(res['node_errors'])[:800]}")
    pid = res["prompt_id"]
    t0, last = time.time(), -1
    while time.time() - t0 < timeout:
        hist = _json(f"/history/{pid}").get(pid)
        if hist:
            st = hist.get("status", {})
            if st.get("status_str") == "error":
                msgs = [m for m in st.get("messages", []) if m[0] == "execution_error"]
                detail = msgs[0][1].get("exception_message", "") if msgs else st
                raise ComfyError(f"ComfyUI failed: {str(detail)[:800]}")
            if st.get("completed") or hist.get("outputs"):
                return hist.get("outputs", {})
        el = int(time.time() - t0)
        if el // 15 != last:
            last = el // 15
            log(f"image3d: running ({el}s)")
        time.sleep(1.0)
    raise ComfyError(f"ComfyUI job {pid} did not finish in {timeout:.0f}s")


def fetch(item: dict) -> bytes:
    """Download one output (a SavedResult dict: filename, subfolder, type)."""
    q = urllib.parse.urlencode({"filename": item["filename"], "subfolder": item.get("subfolder", ""),
                                "type": item.get("type", "output")})
    with urllib.request.urlopen(f"{COMFY}/view?{q}", timeout=120) as r:
        return r.read()


# ---------------------------------------------------------------------------------------------- workflows (API format)

def mask_workflow(images: list[str], prefix: str) -> dict:
    """One BiRefNet foreground mask per image, saved as greyscale PNGs (output index = image index)."""
    wf: dict = {"bg": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": BG_MODEL}}}
    for i, name in enumerate(images):
        wf[f"load{i}"] = {"class_type": "LoadImage", "inputs": {"image": name}}
        wf[f"rm{i}"] = {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["bg", 0], "image": [f"load{i}", 0]}}
        wf[f"img{i}"] = {"class_type": "MaskToImage", "inputs": {"mask": [f"rm{i}", 0]}}
        wf[f"save{i}"] = {"class_type": "SaveImage", "inputs": {"images": [f"img{i}", 0], "filename_prefix": f"{prefix}_mask{i}"}}
    return wf


def mesh_workflow(views: dict[str, str], prefix: str, seed: int = 0, steps: int = 30, cfg: float = 5.0,
                  octree: int = 256) -> dict:
    """Hunyuan3D shape generation. views: {"image": name} for one picture (Hunyuan3D 2.1), or any of
    {"front", "left", "back", "right"} for multi-view (Hunyuan3D-2mv). Writes a GLB through SaveGLB."""
    multi = "image" not in views
    wf: dict = {
        "ckpt": {"class_type": "ImageOnlyCheckpointLoader", "inputs": {"ckpt_name": MODEL_MULTI if multi else MODEL_SINGLE}},
        "ms": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["ckpt", 0], "shift": 1.0}},
    }
    enc = {}
    for key, name in views.items():
        wf[f"load_{key}"] = {"class_type": "LoadImage", "inputs": {"image": name}}
        wf[f"enc_{key}"] = {"class_type": "CLIPVisionEncode",
                            "inputs": {"clip_vision": ["ckpt", 1], "image": [f"load_{key}", 0], "crop": "none"}}
        enc[key] = [f"enc_{key}", 0]
    if multi:
        wf["cond"] = {"class_type": "Hunyuan3Dv2ConditioningMultiView", "inputs": enc}
    else:
        wf["cond"] = {"class_type": "Hunyuan3Dv2Conditioning", "inputs": {"clip_vision_output": enc["image"]}}
    wf["latent"] = {"class_type": "EmptyLatentHunyuan3Dv2", "inputs": {"resolution": 3072 if multi else 4096, "batch_size": 1}}
    wf["ks"] = {"class_type": "KSampler", "inputs": {
        "model": ["ms", 0], "positive": ["cond", 0], "negative": ["cond", 1], "latent_image": ["latent", 0],
        "seed": seed, "steps": steps, "cfg": cfg, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0}}
    wf["dec"] = {"class_type": "VAEDecodeHunyuan3D",
                 "inputs": {"samples": ["ks", 0], "vae": ["ckpt", 2], "num_chunks": 8000, "octree_resolution": octree}}
    wf["mesh"] = {"class_type": "VoxelToMesh", "inputs": {"voxel": ["dec", 0], "algorithm": "surface net", "threshold": 0.6}}
    wf["save"] = {"class_type": "SaveGLB", "inputs": {"mesh": ["mesh", 0], "filename_prefix": prefix}}
    return wf
