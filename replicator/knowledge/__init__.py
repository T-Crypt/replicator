"""Knowledge cards: short, curated notes on how real things are built and sized, picked for a request by keyword.

A local 27B model plans better from a page of real proportions than from memory. Each card is one markdown file
with a `keywords:` line in its front matter; the request's words choose at most two cards.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

DIR = Path(__file__).parent


@dataclass(frozen=True)
class Card:
    name: str
    title: str
    keywords: tuple[str, ...]
    body: str


def _parse(path: Path) -> Card:
    head, body = path.read_text().split("\n---\n", 1)
    meta = dict(line.split(":", 1) for line in head.strip("-\n").splitlines() if ":" in line)
    kws = tuple(k.strip().lower() for k in meta["keywords"].split(",") if k.strip())
    return Card(path.stem, meta["title"].strip(), kws, body.strip())


CARDS = [_parse(p) for p in sorted(DIR.glob("*.md"))]


def pick(request: str, limit: int = 2) -> list[Card]:
    text = " " + re.sub(r"[^a-z0-9]+", " ", request.lower()) + " "
    scored = [(sum(f" {k} " in text for k in c.keywords), c) for c in CARDS]
    return [c for score, c in sorted(scored, key=lambda t: -t[0]) if score][:limit]


def block(request: str) -> str:
    cards = pick(request)
    if not cards:
        return ""
    parts = [f"## {c.title}\n{c.body}" for c in cards]
    return ("\nREFERENCE NOTES (curated facts about how this kind of object is really built; follow its proportions "
            "and part list):\n\n" + "\n\n".join(parts) + "\n")
