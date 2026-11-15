"""Flange: a fully stated machine part. Every graded number is in the prompt, so a program can
satisfy it without guessing."""
from __future__ import annotations

import math
import random

from ..score import Assertion, Instance

NAME = "flange"
CLASS = "spec"
CATEGORY = "machine"


def instance(seed: int) -> Instance:
    rng = random.Random(seed)
    bore = rng.randrange(20, 65, 5)
    od = bore + 2 * rng.randrange(25, 45, 5)
    t = rng.randrange(10, 22, 2)
    n = rng.choice([4, 6, 8])
    h = rng.choice([8, 10, 12])
    pcd = round((bore + od) / 2)
    volume = math.pi / 4 * t * (od * od - bore * bore - n * h * h)
    prompt = (f"A flat round pipe flange lying flat (its faces horizontal): outer diameter {od} mm, "
              f"thickness {t} mm, a central through bore of {bore} mm, and {n} through bolt holes of "
              f"{h} mm diameter equally spaced on a {pcd} mm pitch circle. Nothing else.")
    assertions = (
        Assertion("size", {"axis": "x", "target": od, "tol": 0.02}, 1.0, "outer extent X"),
        Assertion("size", {"axis": "z", "target": od, "tol": 0.02}, 1.0, "outer extent Z"),
        Assertion("size", {"axis": "y", "target": t, "tol": 0.05}, 1.0, "thickness Y"),
        Assertion("genus", {"equals": n + 1}, 2.0, "through holes"),
        Assertion("volume", {"target": volume, "tol": 0.03}, 2.0, "solid volume"),
        Assertion("no_blocking", {}, 1.0, "no blocking issues"),
    )
    params = {"bore": bore, "od": od, "t": t, "n": n, "h": h, "pcd": pcd, "volume": volume}
    return Instance(NAME, seed, prompt, assertions, params)
