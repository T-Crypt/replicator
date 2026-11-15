"""House: a functional brief. The floor area is stated in the prompt; everything else is measured
from the built solid (wall height, named parts, the roof checks)."""
from __future__ import annotations

import random

from ..score import Assertion, Instance

NAME = "house"
CLASS = "function"
CATEGORY = "building"


def instance(seed: int) -> Instance:
    rng = random.Random(seed)
    A = rng.randrange(60, 121, 10)
    prompt = (f"A single-storey two-bedroom house with at least {A} square metres inside the exterior "
              f"walls, walls 2.4 to 2.7 m high on a slab, a front door and windows cut into the walls, "
              f"and a pitched gable roof. Name parts with the words wall, roof, door and window.")
    assertions = (
        Assertion("floor_area", {"word": "wall", "min_m2": A}, 2.0, "floor area"),
        Assertion("top_of", {"word": "wall", "min": 2400, "max": 2900}, 1.0, "wall height Y"),
        Assertion("part", {"word": "roof"}, 1.0, "roof present"),
        Assertion("part", {"word": "door"}, 1.0, "door present"),
        Assertion("part", {"word": "window"}, 1.0, "window present"),
        Assertion("no_issues", {"kinds": ["roof"]}, 2.0, "roof checks"),
        Assertion("no_blocking", {}, 1.0, "no blocking issues"),
    )
    return Instance(NAME, seed, prompt, assertions, {"A": A})
