"""Lamp: a functional everyday object. The one stated number is the shade height at rest; the rest
is graded through the knowledge-card proportion and alignment checks."""
from __future__ import annotations

import random

from ..score import Assertion, Instance

NAME = "lamp"
CLASS = "function"
CATEGORY = "everyday"


def instance(seed: int) -> Instance:
    rng = random.Random(seed)
    H = rng.randrange(400, 551, 25)
    prompt = (f"A balanced-arm desk lamp at real scale whose shade, at rest, sits about {H} mm above "
              f"the desk: a heavy base, a lower and an upper arm each with a spring running along it, "
              f"an elbow, and a shade at the end of the upper arm.")
    assertions = (
        Assertion("no_issues", {"kinds": ["proportion", "alignment"]}, 2.0, "proportion and alignment"),
        Assertion("no_issues", {"kinds": ["tips"]}, 1.0, "stays upright"),
        Assertion("size_range", {"axis": "y", "min": 0.9 * H, "max": 1.7 * H}, 1.0, "shade height Y"),
        Assertion("part", {"word": "shade"}, 1.0, "shade present"),
        Assertion("part", {"word": "spring"}, 1.0, "springs present"),
        Assertion("no_blocking", {}, 1.0, "no blocking issues"),
    )
    return Instance(NAME, seed, prompt, assertions, {"H": H})
