# Benchmark

The benchmark scores a model's construction, not its prose. A configured OpenAI-compatible
endpoint (the built-in engines, or `endpoints` in `~/.config/Replicator/services.json`) is asked
to build one object from a one-paragraph prompt. The kernel then measures the solid it actually
produced (extents, through-holes, volume, named parts) and the workshop critic checks the build.
No assertion can be satisfied by a model's self-report.

## Tasks

Each task is a module in `bench/tasks/`, pinned by a seed. The same seed always gives the same
prompt and the same assertions. Two classes:

- `spec` tasks (flange, board) state every graded number in the prompt. A program can only
  score well if it builds the stated shape.
- `function` tasks (house, lamp) state the job and a few numbers. The score leans on the
  knowledge-card proportion checks and on the critic: roof coverage, tipping, wall height.

## Scoring

A trial first passes a gate: the program validates, it builds without error, and at least one
solid shape survives. Failing the gate scores 0. A passing trial gets

    score = 0.7 * (weighted share of passed assertions)
          + 0.3 * (1 with no blocking critic issues, else 1 - 0.25 per issue, never below 0)

Scoring is deterministic. The same program and the same seed give the same score, so a saved
program re-scores to the same number whenever it is scored again.

## Running

    .venv/bin/python -m tools.bench run --engine <name> --task all --seed 13 --trials 3
    .venv/bin/python -m tools.bench report --out bench/results

Each trial saves the program under `<out>/<engine>/<task>/seed<N>/program.json` and appends one
JSON line per trial to `<out>/<engine>/results.jsonl`. The `score` and `prompt` subcommands
rebuild the instance from the seed with no model at all.
