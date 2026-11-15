"""Path-traced README stills: frame a BuildProgram from a three-quarter view and render it with Blender Cycles on
the CPU (the same renderer as Render > Cycles in the app; no GPU).

    .venv/bin/python -m tools.showcase fixtures/gaming_pc_liquid.json [more.json] [--out assets] [--samples 128]
        [--yaw 35] [--pitch 22] [--size 1600x1000]

Writes <out>/showcase-<name>.png and prints the time each took.
"""
from __future__ import annotations

import argparse
import json
import math
import tempfile
import time
from pathlib import Path

import numpy as np

from replicator.core import render
from replicator.core import export as exporter
from replicator.core.evaluate import Evaluator, bounds
from replicator.core.program import check


def camera(lo, hi, yaw: float, pitch: float, size: tuple[int, int], fov: float = 30.0) -> dict:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    c = (lo + hi) / 2
    r = float(np.linalg.norm(hi - lo)) / 2
    y, p = math.radians(yaw), math.radians(pitch)
    d = np.array([math.sin(y) * math.cos(p), math.sin(p), math.cos(y) * math.cos(p)])
    aspect = size[0] / size[1]
    half = math.radians(fov) / 2 * min(1.0, aspect)       # fit the sphere in the narrower dimension
    ext = hi - lo
    tall = ext[1] > max(ext[0], ext[2])
    dist = r / math.sin(half) * (1.05 if tall else 0.86)   # the sphere is loose around flat parts; tall ones need it
    return {"position": (c + d * dist).tolist(), "target": c.tolist(), "fov": fov, "width": size[0],
            "height": size[1], "radius": r, "dof": False}



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("program", nargs="+", type=Path)
    ap.add_argument("--out", type=Path, default=Path("out/showcase"))
    ap.add_argument("--samples", type=int, default=128)
    ap.add_argument("--yaw", type=float, default=35.0)
    ap.add_argument("--pitch", type=float, default=22.0)
    ap.add_argument("--size", default="1600x1000")
    a = ap.parse_args()
    size = tuple(int(v) for v in a.size.split("x"))
    a.out.mkdir(parents=True, exist_ok=True)
    for path in a.program:
        program = check(json.loads(path.read_text()))
        shapes = Evaluator(path.parent).step(program)
        lo, hi = bounds(shapes)
        with tempfile.TemporaryDirectory() as tmp:
            glb = exporter.export(shapes, program.get("materials", {}), Path(tmp) / "scene.glb")
            t = time.time()
            png = render.cycles_still(glb, a.out / f"showcase-{path.stem}.png", camera(lo, hi, a.yaw, a.pitch, size),
                                      program.get("materials", {}), ground=float(lo[1]), samples=a.samples,
                                      log=lambda m: None, part_materials={s.id: s.material for s in shapes if s.material})
        print(f"{path}: {png} ({time.time() - t:.0f} s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
