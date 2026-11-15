"""Character sheets (a ComfyUI workflow's multi-view renders; folder $REPLICATOR_SHEETS): find the views, cut them apart, square them up for image-to-3D.

A Holodeck sheet (`characters/sheet-*.png` plus a `.png.json` sidecar with the prompt) shows one character several
times side by side, for example "front view, three-quarter view, side view and back view". This module reads the
view order from the prompt, finds the gutters between the figures and returns one crop per view. Background removal
happens later on the GPU (BiRefNet in ComfyUI); `square_on_white` then centres every view at one shared scale, the
way Hunyuan3D-2mv's training renders were framed. CPU only (numpy + Pillow).
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image

CHARACTERS = Path(os.environ.get("REPLICATOR_SHEETS", "~/ComfyUI/output/characters")).expanduser()
VIEW_WORDS = [("three-quarter", "three-quarter"), ("three quarter", "three-quarter"), ("3/4", "three-quarter"),
              ("front", "front"), ("side", "side"), ("profile", "side"), ("back", "back"), ("rear", "back"),
              ("left", "left"), ("right", "right")]
NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}
DEFAULT_LABELS = {1: ["front"], 2: ["front", "back"], 3: ["front", "side", "back"],
                  4: ["front", "three-quarter", "side", "back"]}


@dataclass
class View:
    label: str
    box: tuple[int, int, int, int]   # x0, y0, x1, y1 in the sheet
    image: Image.Image


def sidecar(path: Path) -> dict:
    """The Holodeck/gen.py metadata next to an output image, or {}."""
    p = Path(str(path) + ".json")
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def view_labels(prompt: str) -> list[str]:
    """View order as the prompt names it ("front view, three-quarter view, side view and back view")."""
    words = re.findall(r"(three[- ]quarter|3/4|front|back|side|profile|rear|left|right)\s+view", prompt.lower())
    canon = dict(VIEW_WORDS)
    out = []
    for w in words:  # the sheet template can repeat; keep first occurrences in order
        lab = canon.get(w, canon.get(w.replace("-", " "), w))
        if lab not in out:
            out.append(lab)
    return out


def view_count(prompt: str, labels: list[str]) -> int:
    m = re.search(r"shown (\w+) times", prompt.lower())
    if m and m.group(1) in NUMBERS:
        return NUMBERS[m.group(1)]
    return len(labels) or 4


def _profile(img: Image.Image) -> np.ndarray:
    """Per-column 'how much figure is here', robust to a textured backdrop."""
    a = np.asarray(img.convert("RGB"), dtype=np.float32)
    h, w, _ = a.shape
    border = np.concatenate([a[: h // 20].reshape(-1, 3), a[:, : w // 60].reshape(-1, 3), a[:, -w // 60:].reshape(-1, 3)])
    bg = np.median(border, axis=0)
    diff = np.linalg.norm(a - bg, axis=2)
    thr = max(28.0, float(np.percentile(diff, 55)))
    occ = (diff > thr).mean(axis=0)
    k = max(3, w // 80)
    return np.convolve(occ, np.ones(k) / k, mode="same")


def split(img: Image.Image, n: int) -> list[tuple[int, int, int, int]]:
    """n side-by-side figures -> n boxes; each gutter is the emptiest column near its even-split position."""
    w, h = img.size
    if n <= 1:
        return [(0, 0, w, h)]
    prof = _profile(img)
    cuts = [0]
    for i in range(1, n):
        centre = i * w / n
        span = 0.35 * w / n
        lo, hi = int(centre - span), int(centre + span)
        cuts.append(lo + int(np.argmin(prof[lo:hi])))
    cuts.append(w)
    return [(cuts[i], 0, cuts[i + 1], h) for i in range(n)]


def load(path: Path) -> tuple[list[View], dict]:
    """All views of a sheet, labelled, plus its sidecar metadata."""
    meta = sidecar(path)
    prompt = meta.get("prompt", "")
    labels = view_labels(prompt)
    n = view_count(prompt, labels)
    if len(labels) != n:
        labels = DEFAULT_LABELS.get(n, [f"view {i + 1}" for i in range(n)])
    img = Image.open(path).convert("RGB")
    views = [View(lab, box, img.crop(box)) for lab, box in zip(labels, split(img, n))]
    return views, meta


def subject(meta: dict) -> str:
    """The character description without the sheet template ("an orc warlord in bone armour...")."""
    p = meta.get("prompt", "")
    tail = p.split(",")[-1].strip() if "," in p else p
    return tail[:120] or "Holodeck character"


def clean_mask(mask: Image.Image, size: tuple[int, int] | None = None) -> np.ndarray:
    """Float mask in 0..1 that keeps the figure and drops stray specks and watermarks: the largest connected
    region plus any region at least 8 % of its area (a held weapon, a detached cape)."""
    from scipy import ndimage
    m = mask.convert("L")
    if size and m.size != size:
        m = m.resize(size, Image.BILINEAR)
    a = np.asarray(m, dtype=np.float32) / 255.0
    lab, n = ndimage.label(a > 0.5)
    if n > 1:
        areas = ndimage.sum(np.ones_like(a), lab, index=range(1, n + 1))
        keep = [i + 1 for i, ar in enumerate(areas) if ar >= 0.08 * areas.max()]
        a = a * np.isin(lab, keep)
    return a


def square_on_white(rgb: Image.Image, mask: Image.Image, scale: float, size: int = 512) -> Image.Image:
    """Cut the figure out with its mask and centre it on a white square at the given pixels-per-pixel scale."""
    m = clean_mask(mask, rgb.size)
    ys, xs = np.nonzero(m > 0.5)
    if len(xs) == 0:
        raise ValueError("background removal found no figure in this view")
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    a = np.asarray(rgb, dtype=np.float32)
    comp = a * m[..., None] + 255.0 * (1 - m[..., None])
    fig = Image.fromarray(comp[y0:y1, x0:x1].astype(np.uint8))
    fw, fh = max(1, round(fig.width * scale)), max(1, round(fig.height * scale))
    fig = fig.resize((fw, fh), Image.LANCZOS)
    out = Image.new("RGB", (size, size), (255, 255, 255))
    out.paste(fig, ((size - fw) // 2, (size - fh) // 2))
    return out


def shared_scale(masks: list[Image.Image], size: int = 512, border: float = 0.15) -> float:
    """One scale for every view, so the figure keeps the same height in each (largest extent fills 1 - 2*border)."""
    ext = 1
    for mk in masks:
        m = clean_mask(mk) > 0.5
        ys, xs = np.nonzero(m)
        if len(xs):
            ext = max(ext, xs.max() - xs.min() + 1, ys.max() - ys.min() + 1)
    return size * (1 - 2 * border) / ext
