"""Board: a bare PCB with mounting holes and one standing header, dimensions stated in full."""
from __future__ import annotations

import random

from ..score import Assertion, Instance

NAME = "board"
CLASS = "spec"
CATEGORY = "electronics"


def instance(seed: int) -> Instance:
    rng = random.Random(seed)
    W = rng.randrange(60, 101, 5)
    D = rng.randrange(40, 71, 5)
    prompt = (f"A bare circuit board {W} mm along X by {D} mm along Z, 1.6 mm thick, lying flat, with four "
              f"3.2 mm mounting holes, each 3.5 mm in from both edges at the corners, and a 2 x 20 pin header "
              f"(2.54 mm pitch, about 51 x 5 mm footprint, 8.5 mm tall) standing on the top face along one "
              f"long edge. Name the board part 'board' and the header 'header'.")
    assertions = (
        Assertion("size", {"axis": "x", "target": W, "tol": 0.03}, 1.0, "board extent X"),
        Assertion("size", {"axis": "z", "target": D, "tol": 0.03}, 1.0, "board extent Z"),
        Assertion("genus", {"word": "board", "min": 4}, 2.0, "mounting holes"),
        Assertion("part", {"word": "header"}, 1.0, "header present"),
        Assertion("size_range", {"axis": "y", "min": 8, "max": 14}, 1.0, "stack height Y"),
        Assertion("no_blocking", {}, 1.0, "no blocking issues"),
    )
    return Instance(NAME, seed, prompt, assertions, {"W": W, "D": D})
