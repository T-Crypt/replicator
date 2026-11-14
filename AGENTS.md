# Replicator: rules for agents

Replicator is a local 3D build workshop. A sentence becomes a blueprint, the blueprint becomes a **BuildProgram**
(ordered solid-modelling ops), manifold3d builds it, a critic measures it, and the Qt Quick 3D workspace shows it
step by step. You can dissect it, reverse-engineer an imported model, explain it, render it and hand it to Blender.
Everything runs on this machine. Read `README.md` for the product, `docs/DESIGN.md` for direction and
`docs/REQUIREMENTS-workbench.md` for where it is going (fabrication, mechanics, wiring, sourcing).

## Commands

```sh
.venv/bin/python -m pytest -q                                   # all tests, under 2 s; must stay green
.venv/bin/python -m tools.check path/to/program.json            # validate, build, mass, critic; exit 1 on a FIX issue
WAYLAND_DISPLAY=wayland-1 .venv/bin/python -m replicator.app fixtures/rocket_engine.json --software \
    --shot out/x.png [--mode build|dissect|reverse|showcase|present] [--ui materials|commander|preferences]
.venv/bin/python -m tools.rocket_fixture                        # regenerate the reference rocket engine
./launch.sh [program.json | model.glb | bundle.zip]             # the real window (operator's session)
```

`--shot` needs a Wayland socket: a shell without `WAYLAND_DISPLAY` aborts in `QGuiApplication` (Qt's `offscreen`
platform cannot run Quick3D). Look at every shot you take; a shot is the only proof a QML change works.

## Where things live

| Path | Owns |
|---|---|
| `replicator/core/program.py` | BuildProgram schema and validation, JSON Patch, versions on disk, `component_map`, component delete and duplicate |
| `replicator/core/evaluate.py` | the kernel: op dispatch, per-op cache keyed by hash, build step views |
| `replicator/core/ops_advanced.py`, `ops_engineering.py` | op tables (`PRIMITIVES`, `MODIFIERS`): loft, pipe, helix, gear, deform; tube, nozzle, rotor, grille |
| `replicator/core/critique.py` | accuracy checks (`CHECKS` tuple): floating, buried, clipping, off-axis, size, missing, tips |
| `replicator/core/physics.py` | mass, centre of gravity, stands-or-tips, densities by material name |
| `replicator/core/materials.py` | PBR presets (`PRESETS`, grouped Aerospace, Metal, Polymer, Paint, Glow), paint and whole-build swap |
| `replicator/core/importers.py` | `ROUTES`: every importable extension and how it becomes a Y-up GLB |
| `replicator/core/reverse.py`, `assembly.py`, `explain.py` | mesh decomposition and ledger, components and explode, checked explanations |
| `replicator/core/blender_link.py`, `render.py` | Blender MCP round trip, Cycles stills (CPU) |
| `replicator/knowledge/*.md` | curated cards (real parts and proportions), picked by keyword into the dream prompts |
| `replicator/llm/client.py`, `llm/prompts/*.md` | dream (blueprint, program, repair, critique round), edit (optionally scoped), naming, explain |
| `replicator/qt/bridge.py` | the `studio` QObject: every property and slot QML uses |
| `qml/Main.qml` | layout, workspace state and the `actions` registry (menus, shortcuts, right-click menus, Commander) |
| `qml/panels/`, `qml/viewport/`, `qml/Replicator/UI/` | one file per panel; the 3D view; design tokens and controls |
| `fixtures/` | sample programs. `rocket_engine.json` is the accuracy reference; `dirk_engine_v1.json` is kept as a bad example |

## Invariants

1. **One document.** The BuildProgram is the only source of truth. Panels, the critic, mass and exports are views of
   it. Every change is a new validated program pushed through `Studio._set_program` (one undo step).
2. **`core/`, `knowledge/`, `research/` import no Qt.** They are tested headless. Values handed to QML are plain
   Python types: a numpy `float64` crosses the boundary as garbage (this shipped once as "MASS -1000 g").
3. **The model chooses, the code computes.** Proportions come from ops and formulas (`nozzle` draws a Rao bell from a
   throat radius and expansion ratio), facts from knowledge cards, numbers from measurement. Never ask a model for a
   number code can work out.
4. **Measured, not guessed.** Critic issues and mass are measurements; label anything assumed (a fallback density is
   flagged `*` in the status bar). Reverse ledger kinds: observed, inferred, unknown. Explain kinds: cited, measured,
   concept.
5. **Agent edits are patches.** `client.edit` returns RFC 6902 operations; with `scope` (op ids) any change outside the
   scope is sent back to the model as an error. A job result carries `base`; if the program changed while the model
   worked, the result is dropped, never merged over the operator's work.
6. **GPU.** The window draws on the Intel iGPU. Blender, slicers and converters run with `CUDA_VISIBLE_DEVICES=`.
   Models are reached only through llama-swap `:9090` or Strata `:8080` (`ENGINES` in `client.py`). Never load a model
   in-process. One local-model job at a time.
7. **Local only.** No cloud models. Research (Wikipedia, optional SearXNG) is off until the operator enables it and
   sends only search words.
8. **Imports are untrusted.** Archives unpack into their own new folder with path, size and count checks
   (`importers.unpack`). Never execute anything from an imported file.

## BuildProgram in brief

```json
{"version": 1, "name": "...", "units": "mm",
 "materials": {"titanium_ti6al4v": {"base_color": [0.56, 0.54, 0.51], "metalness": 1.0, "roughness": 0.3}},
 "components": [{"id": "chamber", "label": "Thrust Chamber"}],
 "ops": [{"id": "chamber", "op": "nozzle", "label": "Thrust Chamber and Bell", "component": "chamber",
          "material": "titanium_ti6al4v", "params": {"throat_radius": 100, "expansion_ratio": 16, "translate": [0, 800, 0]}}]}
```

- Y up, millimetres, right-handed. Primitives are centred; axisymmetric ops (`cylinder`, `tube`, `torus`, `nozzle`,
  `rotor`, `revolve`) spin around Y. On a body lying along Z give them `"rotate": [90, 0, 0]`; the critic flags a
  ring on the centre line that spins around the wrong axis.
- Placement (`translate`, `rotate` in degrees X then Y then Z, `scale`) is applied last. Radial `array` copies rotate
  around the world origin, so place the source off-axis first.
- An op consumed by a later op disappears; only leaves are visible. A body that houses parts must be hollow (`tube`,
  `shell`, a revolve with an inner wall) or the critic reports the parts inside as buried.
- `component` groups ops into parts the UI, critic, mass, explode and Blender collections all use.
- Op parameter lists come from the tables: `client.op_reference()` prints them.

## Extending it (each is one table entry plus a test)

- **An op:** a builder in `ops_engineering.py` returning a `Manifold`, an entry in its `PRIMITIVES`
  (`name: (required, optional, _wrap_builder(fn))`), a paragraph in `llm/prompts/program.md`, a `bridge.addPrimitive`
  default and a `Create` action in `Main.qml`. The schema and validation pick it up automatically.
- **A critic check:** a function `(Build) -> list[Issue]` added to `CHECKS`. `fix` only for defects a model can repair.
- **A knowledge card:** `replicator/knowledge/<topic>.md` with `title:` and `keywords:` front matter, under 1k tokens,
  real numbers only, and a pick assertion in `tests/test_accuracy.py`.
- **A material:** a `PRESETS` row whose id contains a substance word `physics.DENSITY` knows (`titanium_...`,
  `steel_...`), so its mass is computed, not assumed.
- **An import format:** a `ROUTES` row; reuse an existing kind (`mesh`, `cad`, `blender`, `archive`).
- **A command:** one object in `actions` (`id`, `group`, `title`, `keys`, `icon`, `enabled`, `run`); menus, right-click
  menus (`partMenu`, `sceneMenu`) and Commander list ids. Never hard-code a colour in a panel: use `Theme`.
- **A bridge slot:** validate on a copy, build it with `self._ev.step(prog)` (shared cache), then `_set_program`.
  Model work goes through `_run_job` / `_agent_edit`; never touch `self._program` or Qt objects from the job thread.

## Driving it as an agent

- Write or patch a program, run `tools.check`, fix every `FIX`, then take a `--shot` in build and showcase and look.
- To change one part, scope the edit to that component's ops (`program.component_ops`), as the Rework action does.
- Blender: *Open in Blender* puts one collection per component, objects named by label with custom properties
  `replicator_id` and `replicator_component`; the vendored mcp-for-blender socket listens on `localhost:9876` only.
  *Pull back* reverse-engineers the live scene into Reverse.
- Known limits: no fluid or structural simulation (strength and CFD are planned, not built); the STEP/IGES route
  (cascadio) is untested against a real CAD file; `round` grows a part by its radius (true bevels need Blender).

## Git

Work on a branch, small commits, each one tested. No AI attribution anywhere. Do not push or open a PR unless the
operator asks.
