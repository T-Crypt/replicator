# Replicator

You dream it, you build it. Type an idea; a local model writes a blueprint and a build program; the object
materializes step by step on a 3D workshop floor, editable at every step. The Holodeck's sibling.

```bash
./launch.sh                                   # empty workshop
./launch.sh fixtures/vector_engine.json       # open a program and play its build
.venv/bin/python -m pytest -q tests           # kernel tests
.venv/bin/python -m replicator.app fixtures/vector_engine.json --software --shot out/x.png   # headless frame
```

- `replicator/core/` BuildProgram schema (`program.py`), manifold3d evaluator (`evaluate.py`), GLB/STL export.
- `replicator/llm/` dream (blueprint -> program -> repair) and edit (JSON Patch) against local models only:
  `dirk` (default), `coder`, `agent` on llama-swap :9090, `strata` on :8080.
- `replicator/qt/` the QML bridge, mesh geometry, procedural studio HDRI. `qml/`, `shaders/` the workshop.
- `replicator/gpu.py` pins the window to the Intel iGPU. The RTX card belongs to llama-swap and Berth.

Operator guide: `~/homelab/guide/replicator.md`.
