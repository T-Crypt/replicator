# Contributing

[AGENTS.md](AGENTS.md) is the map for people and coding agents alike. It lists where each part lives, the
invariants every change keeps, and how to add an op, a critic check, a knowledge card, a material, an import format
or a command.

## Set up

```sh
python -m venv .venv && . .venv/bin/activate
pip install -e ".[all]"
python -m pytest -q
```

The suite runs in under 30 seconds and must stay green.

## Make a change

1. Keep each commit to one tested change.
2. For a change to a program or an op, run `python -m tools.check path/to/program.json` and fix every `FIX` line.
3. For a change to the interface, take a shot and look at it:
   `python -m replicator.app replicator/fixtures/rocket_engine.json --software --shot out/x.png`.
   For overlays and narrow windows, use `tools/shot.sh` instead (it needs gamescope).
4. Open a pull request that says what changed for the person using Replicator and how you checked it.

## Ground rules

- Never load a model in-process or open a GPU context from the library. Models are reached only through the
  configured engines.
- No network call the user did not configure.
- Numbers come from code or measurement, not from a model. Label anything assumed.
