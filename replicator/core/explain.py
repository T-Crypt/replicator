"""Explain: how the object on the floor works, as a short presentation where every sentence shows where it came from.

A sentence is one of three kinds, and the kind is checked here, not taken on the model's word:

  cited      a real-world fact. It names a source from the research lane, and it must share real vocabulary with the
             excerpt it cites; a citation to a source that does not say it is thrown out.
  measured   a number from the geometry (sizes, counts). Every number in it must be one Replicator measured.
  concept    the model's reasoning about what a fictional design would do. Allowed only when the object is a concept,
             and the presentation then opens with a notice saying so.

For a real object, a sentence that fails its check is dropped. For a concept it is kept but shown as concept, so a
fictional jet cannon still gets a full walkthrough without anything invented being passed off as a cited fact.
What this guarantees: no sentence is shown as cited without a matching source excerpt. What it cannot guarantee:
that the source itself is right, or that a paraphrase kept every nuance. The sources are listed for that reason.
"""
from __future__ import annotations

import re
import time

import numpy as np

from ..research.lane import stems

MIN_SHARED = 3           # stems a cited sentence must share with its excerpt(s)
MIN_SHARE = 0.34         # ...or this fraction of its own vocabulary
WPM = 165                # reading speed used to time a chapter when no voice plays


def rest_pose(shapes) -> str:
    """'flush' when the object has a real footprint to stand on, 'levitate' when it would only touch the floor
    along a line or a point (a pod, an engine, a ball): those are shown floating, as a product display would."""
    try:
        V = np.vstack([s.arrays()[0] for s in shapes])
    except (ValueError, AttributeError):
        return "flush"
    if len(V) < 8:
        return "flush"
    lo, hi = V.min(0), V.max(0)
    h = max(hi[1] - lo[1], 1e-6)
    foot = V[V[:, 1] <= lo[1] + 0.02 * h]
    area = max((hi[0] - lo[0]) * (hi[2] - lo[2]), 1e-9)
    if len(foot) < 3:
        return "levitate"
    f = (np.ptp(foot[:, 0]) * np.ptp(foot[:, 2])) / area
    return "flush" if f >= 0.22 else "levitate"


def component_facts(comps, dims: list[float], units: str = "mm") -> list[dict]:
    facts = [{"id": "", "what": "whole object", "size": [round(d, 1) for d in dims], "units": units,
              "components": len(comps)}]
    for c in comps:
        facts.append({"id": c.id, "label": c.label, "role": c.role, "pieces": len(c.shapes),
                      "size": (c.hi - c.lo).round(1).tolist(), "center": c.center.round(1).tolist()})
    return facts


def at_a_glance(subject: str, comps, dims: list[float], units: str = "mm") -> dict:
    """The one chapter written by code: it only repeats measurements, so it is always right."""
    size = " by ".join(f"{d:,.0f}" for d in dims)
    biggest = max(comps, key=lambda c: float(np.prod(c.hi - c.lo)), default=None)
    s = [{"kind": "measured", "text": f"{subject} measures {size} {units}.", "cite": []},
         {"kind": "measured", "text": f"It is made of {len(comps)} component" + ("s." if len(comps) != 1 else "."),
          "cite": []}]
    if biggest is not None and len(comps) > 1:
        s.append({"kind": "measured", "text": f"The largest is the {biggest.label}.", "cite": []})
    return {"title": "At a glance", "component": "", "sentences": s}


def _numbers(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"(?<![\w.])\d[\d,]*\.?\d*", text)]


def verify(raw: dict, sources: list[dict], facts: list[dict], force_concept: bool = False) -> dict:
    """Keep only what can be backed. Returns {concept, concept_note, chapters, dropped, relabelled}."""
    concept = bool(raw.get("concept")) or force_concept
    by_n = {s["n"]: stems(" ".join(s["excerpts"]) + " " + s["title"]) for s in sources}
    known = set()
    for f in facts:
        for v in f.values():
            for x in (v if isinstance(v, list) else [v]):
                if isinstance(x, (int, float)) and not isinstance(x, bool):
                    known |= {round(float(x)), round(float(x), 1)}
    ids = {f["id"] for f in facts}
    dropped = relabelled = 0
    chapters = []
    for ch in raw.get("chapters", [])[:8]:
        if not isinstance(ch, dict):
            continue
        out = []
        for s in (ch.get("sentences") or [])[:5]:
            if not isinstance(s, dict) or not str(s.get("text", "")).strip():
                continue
            text = re.sub(r"\s*\[\d+(?:,\s*\d+)*\]", "", str(s["text"]).strip())[:320]
            kind = s.get("kind")
            cites = [int(c) for c in (s.get("cite") or []) if isinstance(c, (int, float)) and int(c) in by_n]
            ok = False
            if kind == "cited" and cites:
                mine = stems(text)
                shared = len(mine & set().union(*(by_n[c] for c in cites)))
                ok = shared >= MIN_SHARED or (mine and shared / len(mine) >= MIN_SHARE)
            elif kind == "measured":
                nums = _numbers(text)
                ok = bool(nums) and all(round(x) in known or round(x, 1) in known for x in nums)
                cites = []
            elif kind == "concept":
                ok, cites = concept, []
            if not ok and concept and kind != "concept":
                kind, cites, ok = "concept", [], True          # kept, but shown as the design's intent
                relabelled += 1
            if ok:
                out.append({"kind": kind, "text": text, "cite": cites})
            else:
                dropped += 1
        if out:
            comp = ch.get("component") or ""
            chapters.append({"title": str(ch.get("title", "")).strip()[:60] or "Part",
                             "component": comp if comp in ids else "", "sentences": out})
    return {"concept": concept, "concept_note": str(raw.get("concept_note", "")).strip()[:240],
            "chapters": chapters, "dropped": dropped, "relabelled": relabelled}


def finish(subject: str, checked: dict, glance: dict, sources: list[dict], rest: str, engine: str) -> dict:
    """The explanation document saved beside the program and played by Present."""
    chapters = [glance] + checked["chapters"]
    used = {c for ch in chapters for s in ch["sentences"] for c in s["cite"]}
    for ch in chapters:
        text = " ".join(s["text"] for s in ch["sentences"])
        ch["text"] = text
        ch["seconds"] = round(max(4.0, len(text.split()) / WPM * 60 + 1.5), 1)
    counts = {k: sum(1 for ch in chapters for s in ch["sentences"] if s["kind"] == k)
              for k in ("cited", "measured", "concept")}
    note = checked["concept_note"] or "This is a concept: a designed object, not a real product."
    return {"subject": subject, "concept": checked["concept"],
            "notice": ("Concept. " + note + " Real-world principles are cited; everything about this design itself "
                       "is the model's reasoning about what it would do.") if checked["concept"] else "",
            "rest": rest, "chapters": chapters, "sources": [s for s in sources if s["n"] in used],
            "sources_read": len(sources), "counts": counts, "dropped": checked["dropped"],
            "relabelled": checked["relabelled"], "engine": engine, "made": time.strftime("%Y-%m-%d %H:%M")}
