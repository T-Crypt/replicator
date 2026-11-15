"""Golden dreams: run client.dream on a fixed prompt list and record how many tries and fixes each one cost.

    .venv/bin/python -m tools.golden [--force] [--engine NAME] [--only SLUG] [--dir out/golden]

One model job at a time. A prompt with an existing result is skipped unless --force.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

from replicator.llm import client

PROMPTS = [
    "a gas-generator rocket engine with a turbopump and regenerative nozzle",
    "a mid-tower gaming PC with a glass side panel",
    "a powered lower-body exoskeleton in titanium and carbon fibre",
    "a quadcopter drone with 7 inch props",
]


def slug(prompt: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", prompt.lower()).strip("_")[:40]


def run(prompt: str, engine: str) -> dict:
    lines: list[str] = []

    def log(m):
        lines.append(m)
        print("   ", m, flush=True)

    replies: list[str] = []
    real_chat = client.chat
    client.chat = lambda *a, **k: (replies.append(real_chat(*a, **k)), replies[-1])[1]
    t0 = time.time()
    rec = {"prompt": prompt, "engine": engine}
    try:
        prog = client.dream(prompt, engine, log=log)
    except Exception as e:  # a failed dream is a result too
        prog, rec["failed"] = None, f"{type(e).__name__}: {str(e)[:300]}"
    client.chat = real_chat
    rec["seconds"] = round(time.time() - t0, 1)
    rounds = [m for m in lines if m.startswith("program: round")]
    rec["program_rounds"] = len(rounds)
    rec["round_errors"] = [m[len("program: "):][:600] for m in lines if re.match(r"program: \d+ problems", m)]
    rec["first_try_valid"] = len(rounds) == 1 and "failed" not in rec
    rec["log"] = lines
    if rec["round_errors"]:
        rec["failed_replies"] = [r[-5000:] for r in replies[-len(rounds):-1]] if len(rounds) > 1 else []
    if prog:
        issues = client.accuracy(prog)
        rec["fix"] = sum(i.severity == "fix" for i in issues)
        rec["warn"] = sum(i.severity == "warn" for i in issues)
        rec["issues"] = [i.message for i in issues][:12]
        rec["census"] = dict(Counter(o["op"] for o in prog["ops"]))
        rec["program"] = prog
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--engine", default="")
    ap.add_argument("--only", help="slug substring")
    ap.add_argument("--dir", default="out/golden")
    a = ap.parse_args()
    out = Path(a.dir)
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for p in PROMPTS:
        s = slug(p)
        if a.only and a.only not in s:
            continue
        f = out / f"{s}.json"
        if f.exists() and not a.force:
            print(f"skip {s} (result exists)")
        else:
            print(f"run {s}", flush=True)
            f.write_text(json.dumps(run(p, a.engine), indent=1))
        rows.append((s, json.loads(f.read_text())))
    print(f"\n{'prompt':<42}{'sec':>7}{'rounds':>7}{'FIX':>5}{'WARN':>5}  census")
    for s, r in rows:
        census = " ".join(f"{k}:{v}" for k, v in sorted(r.get("census", {}).items()))
        print(f"{s:<42}{r['seconds']:>7}{r['program_rounds']:>7}{r.get('fix', '-'):>5}{r.get('warn', '-'):>5}  "
              f"{r.get('failed') or census}")
        for i, e in enumerate(r["round_errors"]):
            print(f"    round {i + 1} errors: {e[:240]}")
    print(f"first-try valid: {sum(r['first_try_valid'] for _, r in rows)}/{len(rows)}; "
          f"total {sum(r['seconds'] for _, r in rows):.0f} s; FIX {sum(r.get('fix', 0) for _, r in rows)}")


if __name__ == "__main__":
    main()
