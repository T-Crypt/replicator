"""Image or Holodeck sheet -> clean, real-scale GLB that Reverse can take apart.

    sheet / picture --split (CPU)--> views --BiRefNet (GPU)--> masks --square on white, one scale (CPU)-->
    Hunyuan3D-2mv (sheet: front/left/back/right) or Hunyuan3D 2.1 (one picture) --> raw GLB (file units ~ +-1)
    --decimate, stand on the floor, scale to millimetres (CPU)--> <out>/model.glb

Both GPU jobs run in your ComfyUI (`comfy.acquire` / `comfy.release`, with an optional GPU hand-off bridge), so
nothing loads a model in this process. Everything else runs on the CPU in this process.

CLI (no UI): python -m replicator.image3d.pipeline <image-or-sheet.png> [--out DIR] [--single] [--side-as right]
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
from PIL import Image

from . import comfy, sheet

OUT = Path(__file__).resolve().parents[2] / "out" / "image3d"
MV_KEYS = {"front": "front", "back": "back", "left": "left", "right": "right"}


def is_sheet(path: Path, meta: dict | None = None) -> bool:
    meta = meta if meta is not None else sheet.sidecar(path)
    wf = str(meta.get("workflow") or meta.get("ui", {}).get("wf") or "")
    return wf.startswith("sheet") or "/characters/" in str(path) or "reference sheet" in meta.get("prompt", "")


def _views_for(path: Path, single: bool, side_as: str):
    """[(label, mv_key or "image", PIL image)], plus metadata."""
    meta = sheet.sidecar(path)
    if is_sheet(path, meta) and not single:
        views, meta = sheet.load(path)
        out = []
        for v in views:
            key = MV_KEYS.get(v.label) or (side_as if v.label == "side" else None)
            if key and key not in [k for _, k, _ in out]:
                out.append((v.label, key, v.image))
        if len(out) >= 2:
            return out, meta, "multi"
        front = next((v for v in views if v.label == "front"), views[0])
        return [(front.label, "image", front.image)], meta, "single"
    return [("image", "image", Image.open(path).convert("RGB"))], meta, "single"


def finish_mesh(raw: Path, dest: Path, height_mm: float, max_faces: int, log=print) -> tuple[dict, list]:
    """Clean the generated surface and bring it to real scale. Returns (stats, pieces).

    Surface extraction leaves thousands of specks around fur and thin edges; only connected parts with at least
    0.5 % of the largest part's faces stay (horns, plates, a held weapon). The kept parts are decimated to max_faces
    in total, stood on the floor (min Y = 0), centred on X/Z and scaled to height_mm."""
    import trimesh
    mesh = trimesh.load(raw, force="scene").to_geometry()
    tri0 = len(mesh.faces)
    mesh.merge_vertices()
    parts = sorted(mesh.split(only_watertight=False), key=lambda m: -len(m.faces))
    keep = [m for m in parts if len(m.faces) >= 0.005 * len(parts[0].faces)][:12]
    dropped = len(parts) - len(keep)
    kept_faces = sum(len(m.faces) for m in keep)
    if kept_faces > max_faces:
        keep = [m.simplify_quadric_decimation(face_count=max(200, int(len(m.faces) * max_faces / kept_faces)))
                for m in keep]
    whole = trimesh.util.concatenate(keep)
    lo, hi = whole.bounds
    s = height_mm / (float(hi[1] - lo[1]) or 1.0)
    shift = [-(lo[0] + hi[0]) / 2, -lo[1], -(lo[2] + hi[2]) / 2]
    for m in keep:
        m.apply_translation(shift)
        m.apply_scale(s)
    whole = trimesh.util.concatenate(keep)
    whole.visual = trimesh.visual.ColorVisuals(whole, face_colors=[200, 202, 206, 255])
    whole.export(dest)
    log(f"image3d: {tri0:,} triangles in {len(parts):,} parts -> kept {len(keep)} parts, "
        f"{len(whole.faces):,} triangles ({dropped:,} specks dropped)")
    ext = whole.bounds[1] - whole.bounds[0]
    stats = {"triangles_raw": tri0, "triangles": int(len(whole.faces)), "parts_raw": len(parts),
             "parts": len(keep), "specks_dropped": dropped, "size_mm": [round(float(x), 1) for x in ext],
             "watertight_parts": int(sum(m.is_watertight for m in keep)), "scale": s}
    return stats, keep


def write_program(out: Path, info: dict, pieces: list) -> tuple[dict, dict]:
    """A BuildProgram (one `mesh` op per kept part, one component) and a Reverse report with an evidence ledger."""
    from ..core.reverse import ledger_entry
    assets = out / "assets"
    assets.mkdir(exist_ok=True)
    name = info["subject"][:1].upper() + info["subject"][1:]
    comp = {"id": "c1", "label": name[:60], "role": "generated from " + ("a character sheet" if info["kind"] == "multi"
                                                                       else "a picture"), "evidence": "image to 3D"}
    ops = []
    for i, m in enumerate(pieces):
        rel = f"assets/part_{i:02d}.npz"
        np.savez_compressed(out / rel, V=np.asarray(m.vertices, np.float32), F=np.asarray(m.faces, np.uint32))
        ops.append({"id": "body" if i == 0 else f"part{i}", "op": "mesh", "label": "Body" if i == 0 else f"Detached part {i}",
                    "part": "body" if i == 0 else "detached", "component": "c1", "material": "clay", "params": {"asset": rel}})
    views = ", ".join(f"{lab} as {key}" if key != "image" else lab for lab, key in info["views"])
    src = Path(info["source"]).name
    ledger = [
        ledger_entry(f"shape generated by {info['model'].split('.')[0]} from {len(info['views'])} view(s) of {src}",
                     "observed", f"views used: {views}; seed {info['seed']}; {info['gpu_seconds']} s on the card"),
        ledger_entry(f"{info['parts_raw']:,} connected parts, {info['triangles_raw']:,} triangles in the raw surface",
                     "observed", "VoxelToMesh surface net, threshold 0.6"),
        ledger_entry(f"kept {info['parts']} part(s), {info['triangles']:,} triangles; {info['specks_dropped']:,} specks dropped",
                     "observed", "parts under 0.5 % of the largest are noise from the surface extraction"),
        ledger_entry("overall size {:.0f} x {:.0f} x {:.0f} mm".format(*info["size_mm"]), "inferred",
                     f"height set to {info['size_mm'][1]:.0f} mm (a sheet is read as a person-sized figure); "
                     "change it with Scale", confidence=0.4),
        ledger_entry("surfaces hidden in every view (under arms, between legs) are the model's guess", "inferred",
                     "image-to-3D completes what no view shows", confidence=0.5),
        ledger_entry("materials and colours", "unknown", "shape only: Hunyuan3D shape models make no texture"),
    ]
    checklist = [
        {"q": "What does it look like in 3D?", "status": "answered", "by": "generated shape"},
        {"q": "What is it made of?", "status": "partly answered", "by": f"{len(ops)} connected part(s)"},
        {"q": "How big is it?", "status": "partly answered", "by": "assumed height; set the real one"},
        {"q": "What material is each part?", "status": "unresolved", "by": "no texture yet (M3 next: AI texturing)"},
    ]
    program = {"version": 1, "name": name, "units": "mm",
               "materials": {"clay": {"base_color": [0.78, 0.76, 0.72], "metalness": 0.0, "roughness": 0.62}},
               "components": [comp], "ops": ops,
               "reference": {"source": info["source"],
                             "views": [{"label": lab, "key": key, "image": f"views/{key}.png"} for lab, key in info["views"]]},
               "blueprint": {"summary": f"Generated from {src} by {info['model'].split('.')[0]}: {views}.",
                             "source": info["source"]}}
    report = {"input": {"file": src, "format": "image to 3D"}, "ledger": ledger, "checklist": checklist,
              "patterns": [], "components": [comp]}
    (out / "program.json").write_text(json.dumps(program, indent=1))
    (out / "reverse_report.json").write_text(json.dumps(report, indent=1))
    return program, report


def image_to_mesh(src: Path, out: Path | None = None, *, single: bool = False, side_as: str = "left",
                  height_mm: float | None = None, seed: int = 0, max_faces: int = 150_000, log=print) -> dict:
    src = Path(src)
    out = out or OUT / (src.stem + time.strftime("-%Y%m%d-%H%M%S"))
    vdir = out / "views"
    vdir.mkdir(parents=True, exist_ok=True)
    views, meta, kind = _views_for(src, single, side_as)
    log(f"image3d: {src.name}: {len(views)} view(s) [{', '.join(f'{lab}->{key}' for lab, key, _ in views)}]")
    crops = []
    for lab, key, img in views:
        p = vdir / f"{key}_crop.png"
        img.save(p)
        crops.append(p)
    tag = f"replicator/{out.name}"
    t0 = time.time()
    comfy.acquire(log)
    try:
        names = [comfy.upload(p) for p in crops]
        res = comfy.run(comfy.mask_workflow(names, tag), log)
        masks = []
        for i in range(len(views)):
            item = res[f"save{i}"]["images"][0]
            mp = vdir / f"{views[i][1]}_mask.png"
            mp.write_bytes(comfy.fetch(item))
            masks.append(Image.open(mp))
        scale = sheet.shared_scale(masks)
        cond = {}
        for (lab, key, img), mk in zip(views, masks):
            sq = sheet.square_on_white(img, mk, scale)
            p = vdir / f"{key}.png"
            sq.save(p)
            cond[key] = comfy.upload(p)
        model = comfy.MODEL_MULTI if kind == "multi" else comfy.MODEL_SINGLE
        log(f"image3d: generating the shape with {model}")
        res = comfy.run(comfy.mesh_workflow(cond, tag, seed=seed), log)
        item = res["save"]["3d"][0]
        raw = out / "raw.glb"
        raw.write_bytes(comfy.fetch(item))
    finally:
        comfy.release()
    gpu_s = time.time() - t0
    log(f"image3d: shape ready in {gpu_s:.0f}s; the card is released")
    if height_mm is None:
        height_mm = 1800.0 if kind == "multi" or is_sheet(src, meta) else 300.0
    dest = out / "model.glb"
    stats, pieces = finish_mesh(raw, dest, height_mm, max_faces, log)
    info = {"source": str(src), "kind": kind, "model": model, "views": [[lab, key] for lab, key, _ in views],
            "subject": sheet.subject(meta) if meta.get("prompt") else src.stem.replace("_", " "), "seed": seed,
            "gpu_seconds": round(gpu_s, 1), "glb": str(dest), "raw": str(raw), **stats}
    (out / "image3d.json").write_text(json.dumps(info, indent=1))
    write_program(out, info, pieces)
    info["program"] = str(out / "program.json")
    return info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("image")
    ap.add_argument("--out")
    ap.add_argument("--single", action="store_true", help="use one picture (the front view of a sheet)")
    ap.add_argument("--side-as", default="left", choices=["left", "right"], help="which Hunyuan view a sheet's side view is")
    ap.add_argument("--height", type=float, help="model height in mm (sheet default 1800, picture default 300)")
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--max-faces", type=int, default=150_000)
    a = ap.parse_args()
    info = image_to_mesh(Path(a.image), Path(a.out) if a.out else None, single=a.single, side_as=a.side_as,
                         height_mm=a.height, seed=a.seed, max_faces=a.max_faces)
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
