"""What the start screen offers: the bundled examples, the user's recent builds and reverse-engineering projects.
Only the head of each JSON file is parsed for the name and step count, and only the newest few files are read."""
from __future__ import annotations

import json
import time
from functools import lru_cache
from pathlib import Path

from .. import FIXTURES
from ..image3d.pipeline import OUT as IMAGE3D_OUT

RECENT_LIMIT = 8


def _row(path: Path, kind: str) -> dict | None:
    try:
        prog = json.loads(path.read_text())
        ops = prog["ops"]
    except (OSError, ValueError, KeyError, TypeError):
        return None
    kinds: dict[str, int] = {}
    for op in ops:
        kinds[op.get("op", "?")] = kinds.get(op.get("op", "?"), 0) + 1
    comps = {op.get("component") or op.get("part") or op["id"] for op in ops}
    top = sorted(kinds, key=lambda k: -kinds[k])[:3]
    mt = path.stat().st_mtime
    return {"path": str(path), "name": prog.get("name") or path.stem, "kind": kind, "steps": len(ops),
            "components": len(comps), "ops": ", ".join(top), "mtime": mt,
            "when": time.strftime("%d %b %H:%M", time.localtime(mt)),
            "summary": ((prog.get("blueprint") or {}).get("summary") or "")[:160]}


def examples() -> list[dict]:
    rows = [_row(p, "example") for p in sorted(FIXTURES.glob("*.json"))]
    return [r for r in rows if r]


def recents(out: Path) -> list[dict]:
    files: list[tuple[Path, str]] = [(p, "dream") for p in out.glob("*.json")]
    files += [(p, "reverse") for p in (out / "reverse").glob("*/program.json")]
    files += [(p, "image") for p in IMAGE3D_OUT.glob("*/program.json")]
    files.sort(key=lambda t: -t[0].stat().st_mtime)
    rows, seen = [], set()
    for p, kind in files[:RECENT_LIMIT * 4]:        # repeated runs of one subject show once, newest first
        r = _row(p, kind)
        if r and (kind, r["name"]) not in seen:
            seen.add((kind, r["name"]))
            rows.append(r)
        if len(rows) == RECENT_LIMIT:
            break
    return rows


@lru_cache(maxsize=64)
def figure_extent(path: Path) -> tuple[float, float]:
    """How much of a reference view's height the figure fills, and where its middle sits (0 top .. 1 bottom).
    The viewport uses it to stand the picture at exactly the model's height."""
    import numpy as np
    from PIL import Image
    try:
        a = np.asarray(Image.open(path).convert("L").resize((128, 128)))
    except OSError:
        return 0.7, 0.5
    rows = np.nonzero((a < 235).sum(axis=1) > 1)[0]
    if len(rows) < 4:
        return 0.7, 0.5
    return float((rows[-1] - rows[0] + 1) / 128), float((rows[0] + rows[-1] + 1) / 2 / 128)
