"""Benchmark runner: dream a task instance through a configured engine, score the built solid, and
collect one JSON line per trial; report reads the collected lines back as markdown tables.

    .venv/bin/python -m tools.bench run --engine local --task all --seed 13 --trials 3
    .venv/bin/python -m tools.bench score replicator/fixtures/house_two_bed.json --task house --seed 13
    .venv/bin/python -m tools.bench prompt --task flange --seed 13
    .venv/bin/python -m tools.bench report --out bench/results

Scoring is deterministic: the same program and the same task seed give the same score, whatever model
dreamed the program up.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

from bench import tasks
from bench.score import score
from replicator.llm import client


def task_hash(module) -> str:
    """First 16 hex of the sha256 of the task module's source: a stable tag for the prompt and the assertions."""
    return hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()[:16]


def _commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - not a git checkout (or git missing): the row just says so
        return "unknown"


def _pick_tasks(name: str) -> list[str]:
    if name == "all":
        return sorted(tasks.TASKS)
    if name not in tasks.TASKS:
        raise ValueError(f"unknown task {name!r}; known: {', '.join(sorted(tasks.TASKS))}")
    return [name]


def run(engine: str, task: str, seed: int, trials: int, out: Path) -> int:
    known = client.engines()
    if engine not in known:
        print(f"error: unknown engine {engine!r}; known: {', '.join(sorted(known))} "
              f"(add more under endpoints in services.json)", file=sys.stderr)
        return 2
    try:
        names = _pick_tasks(task)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    model, commit = known[engine][1], _commit()
    results = out / engine / "results.jsonl"
    results.parent.mkdir(parents=True, exist_ok=True)
    for name in names:
        module = tasks.TASKS[name]
        for t in range(trials):
            trial_seed = seed + t
            inst = module.instance(trial_seed)
            t0 = time.perf_counter()
            program, failure = None, None
            token = client.SEED.set(trial_seed)
            try:
                program = client.dream(inst.prompt, engine)
            except Exception as e:  # noqa: BLE001 - a trial that cannot be dreamed scores 0 with the reason
                failure = str(e)
            finally:
                client.SEED.reset(token)
            if program is not None:
                trial = out / engine / name / f"seed{trial_seed}"
                trial.mkdir(parents=True, exist_ok=True)
                (trial / "program.json").write_text(json.dumps(program, indent=1) + "\n")
                result = score(program, inst)
            else:
                result = {"score": 0.0, "gate": False, "reason": failure, "assertions": []}
            row = {
                "task": name,
                "task_hash": task_hash(module),
                "class": module.CLASS,
                "category": module.CATEGORY,
                "seed": trial_seed,
                "engine": engine,
                "model": model,
                "commit": commit,
                "prompt": inst.prompt,
                "score": result["score"],
                "gate": result["gate"],
                "blocking": result.get("blocking", 0),
                "assertions": result.get("assertions", []),
                "seconds": round(time.perf_counter() - t0, 2),
            }
            if "reason" in result:
                row["reason"] = result["reason"]
            with results.open("a") as f:
                f.write(json.dumps(row) + "\n")
            mark = "pass" if result["gate"] else "fail"
            why = f" ({result['reason'][:100]})" if result.get("reason") else ""
            print(f"{engine:8} {name:6} seed {trial_seed}: score {result['score']:.3f} {mark}{why}")
    print(f"{trials} trial(s) per task, {len(names)} task(s) -> {results}")
    return 0


def _read_rows(out: Path) -> list[dict]:
    rows = []
    for f in sorted(out.glob("*/*.jsonl")):
        for line in f.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def report(out: Path) -> str:
    rows = _read_rows(out)
    if not rows:
        return f"no results under {out}: run `tools/bench.py run` first"
    lines = ["# Benchmark report", ""]
    by_task: dict[str, list[dict]] = {}
    for r in rows:
        by_task.setdefault(str(r["task"]), []).append(r)
    for task in sorted(by_task):
        lines += [f"## {task}", ""]
        seeds = sorted({int(r["seed"]) for r in by_task[task]})
        engines: dict[tuple[str, str], list[dict]] = {}
        for r in by_task[task]:
            engines.setdefault((str(r["engine"]), str(r.get("model", ""))), []).append(r)
        head = ["engine (model)"] + [f"seed {s}" for s in seeds] + ["mean", "min", "max", "gate"]
        lines.append("| " + " | ".join(head) + " |")
        lines.append("|" + "---|" * len(head))
        for (engine, model) in sorted(engines):
            rs = engines[(engine, model)]
            by_seed = {int(r["seed"]): r for r in rs}
            cells = [f"{by_seed[s]['score']:.2f}" if s in by_seed else "-" for s in seeds]
            sc = [r["score"] for r in rs]
            gates = f"{sum(1 for r in rs if r['gate'])}/{len(rs)}"
            lines.append(f"| {engine} ({model}) | " + " | ".join(cells) + " | "
                         f"{sum(sc) / len(sc):.3f} | {min(sc):.2f} | {max(sc):.2f} | {gates} |")
        lines.append("")
    engines = sorted({(str(r["engine"]), str(r.get("model", ""))) for r in rows})
    lines += ["## Overall (mean score per engine, across tasks)", ""]
    head = ["engine (model)"] + sorted(by_task) + ["all"]
    lines.append("| " + " | ".join(head) + " |")
    lines.append("|" + "---|" * len(head))
    for engine, model in engines:
        per_task = {}
        for task, rs in by_task.items():
            mine_task = [r for r in rs if (str(r["engine"]), str(r.get("model", ""))) == (engine, model)]
            if mine_task:
                per_task[task] = sum(r["score"] for r in mine_task) / len(mine_task)
        cells = [f"{per_task[t]:.3f}" if t in per_task else "-" for t in sorted(by_task)]
        allm = sum(per_task.values()) / len(per_task) if per_task else 0.0
        lines.append(f"| {engine} ({model}) | " + " | ".join(cells) + f" | {allm:.3f} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="tools.bench", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("run", help="dream, build, score and log trials")
    e.add_argument("--engine", required=True)
    e.add_argument("--task", required=True, help="a task name or all")
    e.add_argument("--seed", type=int, required=True)
    e.add_argument("--trials", type=int, required=True)
    e.add_argument("--out", default="bench/results")
    e = sub.add_parser("score", help="score an existing program against a task instance")
    e.add_argument("program")
    e.add_argument("--task", required=True)
    e.add_argument("--seed", type=int, required=True)
    e = sub.add_parser("prompt", help="print the instance prompt")
    e.add_argument("--task", required=True)
    e.add_argument("--seed", type=int, required=True)
    e = sub.add_parser("report", help="markdown tables over the collected results")
    e.add_argument("--out", default="bench/results")
    a = ap.parse_args(argv)
    if a.cmd == "run":
        return run(a.engine, a.task, a.seed, a.trials, Path(a.out))
    if a.cmd == "score":
        if a.task not in tasks.TASKS:
            print(f"error: unknown task {a.task!r}; known: {', '.join(sorted(tasks.TASKS))}", file=sys.stderr)
            return 2
        path = Path(a.program)
        if not path.is_file():
            print(f"error: {path} does not exist", file=sys.stderr)
            return 2
        program = json.loads(path.read_text())
        inst = tasks.TASKS[a.task].instance(a.seed)
        result = score(program, inst, path.resolve().parent)
        print(json.dumps(result, indent=2))
        return 0
    if a.cmd == "prompt":
        if a.task not in tasks.TASKS:
            print(f"error: unknown task {a.task!r}; known: {', '.join(sorted(tasks.TASKS))}", file=sys.stderr)
            return 2
        print(tasks.TASKS[a.task].instance(a.seed).prompt)
        return 0
    print(report(Path(a.out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
