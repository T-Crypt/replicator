<p align="center"><img src="assets/banner.svg" alt="Replicator: a turbofan engine floats in an exploded view over a night workshop floor while a scan plane turns its cyan blueprint wireframe into solid coloured parts. On the left, a specify prompt and the pipeline blueprint, program, manifold3d, build." width="100%"></p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11%2B-7ad4f2?labelColor=0a1017" alt="Python 3.11 or later">
  <img src="https://img.shields.io/badge/qt-6.9%2B%20%C2%B7%20Quick%203D-7ad4f2?labelColor=0a1017" alt="Qt 6.9 or later, Qt Quick 3D">
  <img src="https://img.shields.io/badge/kernel-manifold3d-7ee8ac?labelColor=0a1017" alt="manifold3d kernel">
  <img src="https://img.shields.io/badge/models-local%20or%20your%20endpoint-e8b56f?labelColor=0a1017" alt="Local models or any endpoint you name">
  <img src="https://img.shields.io/badge/agents-MCP-e8b56f?labelColor=0a1017" alt="Agents over MCP">
  <img src="https://img.shields.io/badge/license-MIT-c4a1ff?labelColor=0a1017" alt="MIT licence">
</p>

<p align="center">
  <a href="#quick-start">Quick start</a> &nbsp;·&nbsp; <a href="#how-it-works">How it works</a> &nbsp;·&nbsp; <a href="#the-buildprogram">BuildProgram</a> &nbsp;·&nbsp; <a href="#modes">Modes</a> &nbsp;·&nbsp; <a href="#agents-mcp">Agents</a> &nbsp;·&nbsp; <a href="#printing-optional">Printing</a> &nbsp;·&nbsp; <a href="#image-to-3d">Image to 3D</a> &nbsp;·&nbsp; <a href="#blender">Blender</a> &nbsp;·&nbsp; <a href="#roadmap">Roadmap</a>
</p>

# Replicator

You specify it, you build it. Describe a thing in a sentence: a house with a floor plan, a circuit
board, a desk lamp, a rocket engine, a liquid-cooled PC, a concept nobody has built yet. A model
plans it from engineering knowledge, writes a build program, and a real solid-modelling kernel
builds it one step at a time. You can stop at any step, change it, take it apart, check it, draw it
and hand it to CAD, a printer or a renderer.

Replicator is an engineer's workshop first and a research tool second. The design is a validated
program, not a picture or generated code, so every part has a size, a material and a mass; nine
automatic checks catch parts that float, clip, stand unstably or miss their planned size; and
Reverse mode takes an existing model apart into pieces with an evidence ledger saying what was
measured, what was inferred and what nobody can tell.

<p align="center"><img src="assets/range.jpg" alt="Six things Replicator built: a liquid-cooled PC with glowing coolant in a glass case, a Raspberry Pi 5 at real scale, a gas-generator rocket engine with a bell nozzle, the PC exploded in Dissect mode with labelled callouts, a two-bedroom house with a gable roof, and that house's drawing sheet with a floor plan and two elevations." width="100%"></p>

<p align="center"><img src="assets/build-timeline.gif" alt="The liquid-cooled PC assembling in the workshop one build step at a time along the timeline, then sliding apart in Dissect mode with callouts on every component." width="900"></p>

You choose the model: a local server (llama.cpp, Ollama, LM Studio, vLLM) or any OpenAI-compatible
endpoint, including a hosted one. Agents such as Claude Code, Codex or Cursor can drive the same
workshop over MCP. The geometry comes from manifold3d on the CPU, so everything except specifying
works with no model at all: open a program, edit it, check it, draw it, export it.

Printing is one output among many. A build can stay a design, become a drawing sheet, go to CAD as
STEP, to a renderer as GLB, to Blender, or to a printer. Nothing needs a printer.

```sh
replicator                                    # an empty workshop
replicator fixtures/house_two_bed.json        # open a program and watch it build
replicator path/to/model.glb                  # take a model apart in Reverse
```

## How it works

<p align="center"><img src="assets/how-it-works.svg" alt="How Replicator works. Five stages: a sentence that specifies the object, a blueprint written by the model you choose, a BuildProgram of ordered operations, the manifold3d kernel that evaluates every step, and the workshop where the steps materialize. Validation errors loop back to the model for repair, and edits in plain words become JSON Patches on the program. Four modes share one scene: Build, Dissect, Reverse and Showcase. Image to 3D and mesh import come in; a Blender round trip and STEP, STL, 3MF or GLB export go out. Geometry, checks and exports run on your CPU; the model is any OpenAI-compatible endpoint you name." width="100%"></p>

1. **Specify.** You type what you want: *"a two-bedroom house with a gable roof"* or *"a turbofan with
   reverse thrust doors"*. With research on, the model looks up real proportions first (only search
   words leave the machine), and curated knowledge cards for houses, electronics boards, desktop PCs,
   drones, light aircraft, rocket engines, turbofans, exoskeletons and car wheel corners feed the plan.
2. **Blueprint.** The model plans the object first: its parts, their sizes in millimetres, the
   materials and how the parts fit together. The plan comes before any geometry, so the model never
   has to invent coordinates on the fly.
3. **BuildProgram.** A second pass turns the blueprint into an ordered list of operations
   (`revolve`, `array`, `boolean`, `loft` and the rest), each tagged with the component it builds.
   The program is plain JSON, validated against a schema generated from the kernel's own op table.
   When an op fails, the errors go back to the model and it repairs the program.
4. **Kernel.** manifold3d evaluates the program. Each op's result is cached by a hash of its inputs,
   so a rebuild after an edit redoes only what changed. A full build takes 10 to 60 ms.
5. **Workshop.** The steps play on the floor. Each new part comes in through a holo shader: a
   wireframe edge pass, a rising scan plane, then a dissolve into the real material.

Build step *k* is ops 0 to *k*. An op that a later op consumes disappears at that step, so every
step shows the object as it stood at that moment, like the construction history in a CAD package.
Buildings get a floor plan instead of a section on their drawing sheet.

Edits work the same way. Type *"make the reverser doors wider"* and the model answers with a JSON
Patch against the program, not a new program. Each save is a version you can step back to.

## What Replicator does

**Builds from a sentence**
- **Two-stage specifying.** A blueprint pass plans the object, then a program pass writes the ops. The
  prompts carry the rules that make engineered shapes look right: hollow bodies get a real wall,
  radial rings follow the body axis, and every op carries a label and a component.
- **Repairs itself.** Validation and kernel errors go back to the model with the failing op, for up
  to two repair rounds. The parser strips the comments, trailing commas and code fences local
  models tend to add.
- **Edits by patch.** An edit is a JSON Patch: applied, validated, then saved as a version. A bad
  patch never replaces a good program.
- **Your choice of model.** The built-in `local` engine (any OpenAI-compatible server, configured by
  environment variables) or any endpoint you add to `services.json` ([Models](#models)).
- **Checks the result.** Nine engineering checks run on every build: floating parts, parts loose in a
  cavity, clipping, array copies, thin walls, off-axis rings, size against the blueprint, planned
  parts that are missing, and whether it stands. Mass, centre of gravity and principal inertia come
  from the material table and the exact solid. A failing check goes back to the model as an edit.

**A real modelling kernel**
- **manifold3d.** Watertight solids, exact booleans and convex hulls. A program can't produce a mesh
  with holes in it.
- **25 operations.** Primitives (`box`, `cylinder`, `sphere`, `torus`, `capsule`, `extrude`,
  `revolve`), builders (`loft`, `pipe`, `helix`, `gear` with involute teeth), engineering ops
  (`tube`, `nozzle` with a Rao bell from throat radius and expansion ratio, `rotor`, `grille`, `wing`
  with NACA sections), modifiers (`transform`, `array` linear/radial/mirror, `smooth`, `round`,
  `shell`, `deform` taper/twist/bend), combiners (`boolean`, `hull`, `group`) and `mesh` for
  imported geometry.
- **Drawing sheets.** An A3 sheet straight from the program: third-angle views, a section (or a floor
  plan for buildings), measured dimensions, numbered callouts and a parts list with computed masses.
- **Exports.** STEP for CAD (exact faceted solids, one per connected lump, cavities kept as voids;
  OpenCASCADE reads every fixture back as valid solids with the same volume), STL and 3MF for
  printers, GLB with materials for engines and the web, OBJ.

**A Cinema 4D-style workspace**
- **Viewport.** A damped orbit camera with zoom to cursor and adaptive clip planes, a perspective
  view and three orthographic ones (`F1` to `F4`), an axis triad, and a move gizmo with snapping
  (`W`). `H` frames everything, `F` frames the selection.
- **Managers.** An Object Manager grouped by component, an Attribute Manager for the selected op's
  parameters and placement, and a console.
- **Timeline.** Every op is a block. Play forward or in reverse, scrub, or jump to any step (`Space`
  plays and pauses).
- **Blueprint morph.** One slider fades the scene from a cyan-on-navy technical drawing to full PBR.

## Modes

| Key | Mode | What it is for |
|---|---|---|
| `1` | **Build** | Watch the build, pick any step, change its parameters or placement, rebuild. |
| `2` | **Dissect** | An exploded view: every part slides out along its own axis, and callouts with leader lines follow the parts. |
| `3` | **Reverse** | Import a model (`Ctrl+I`: 24 formats, including STEP and IGES through OpenCASCADE and FBX, USD and .blend through Blender) and take it apart into pieces, repeated patterns, contacts and a likely assembly order. Every finding sits in an evidence ledger marked *observed*, *inferred* or *unknown*, and *Name parts* asks the model to label the pieces. |
| `4` | **Showcase** | A product stage with soft shadows, ambient occlusion, depth of field and a turntable. *Render* writes a Cycles still on the CPU in about 7 s. |

## Preview

<p align="center"><img src="assets/preview-build.jpg" alt="Build mode: a turbofan specified by a local model on the workshop grid, the Object Manager listing fourteen components, and the timeline with all 22 build steps as coloured blocks." width="900"></p>

<p align="center"><img src="assets/preview-dissect.jpg" alt="Dissect mode: the same engine exploded along its axis with labelled callouts for each component, and the Assembled to Exploded slider." width="900"></p>

<p align="center"><img src="assets/preview-reverse.jpg" alt="Reverse mode: the evidence ledger on the right lists observed facts about the engine, such as 22 build steps producing 15 visible parts and a radial array of 22 fan blades." width="900"></p>

<p align="center"><img src="assets/preview-cycles.jpg" alt="A Showcase still rendered with Cycles on the CPU: the engine on a reflective studio floor with a cyan glow ring inside the intake." width="640"></p>

## Agents (MCP)

`replicator.mcp_server` exposes the workshop to any MCP client. The document is a program file on
disk: every write is validated and built before it replaces the file (the previous version is kept
as `<name>.prev.json`), so an agent can never leave a broken program behind. A Replicator window
with the same file open reloads it on change, and the agent's edit lands on the timeline as one undo
step.

| Tool | What it does |
|---|---|
| `op_reference` | The op vocabulary, generated from the kernel's own table |
| `read_program`, `write_program`, `patch_program` | Read, create, or change by RFC 6902 JSON Patch |
| `build_report` | Size, mass, components and every check, for the whole build or ops 0 to *k* |
| `export` | STEP, STL, 3MF, GLB or OBJ |
| `drawing_sheet` | The A3 sheet as SVG and PNG |
| `specify` | A new program from a sentence, on any configured engine |
| `engines` | Which models `specify` can use |
| `reverse` | Take an existing model apart into a program with its evidence ledger |

This repo's `.mcp.json` registers it for Claude Code; for another client, run
`python -m replicator.mcp_server` over stdio.

## Benchmark and corpus

`bench/` scores any engine on construction, not prose: four seeded tasks (a flange, a circuit board,
a house, a desk lamp) whose dimensions move with the seed, scored by measuring the built solid
(extents, through-holes, volume, named parts, floor area) and by the checks. The same program and
seed always score the same. See [bench/README.md](bench/README.md).

```sh
python -m tools.bench run --engine local --task all --seed 13 --trials 3
python -m tools.bench report
```

`tools/corpus.py export` turns a folder of programs into JSONL rows (prompt, program, geometry digest,
mass, verdict) for training or evaluation, and `verify` rebuilds every row to prove it still holds.

## Quick start

Python 3.11 or later. Tested on Linux (X11 and Wayland); macOS and Windows should work wherever
PySide6 and manifold3d install, but nobody has tested them yet.

```sh
git clone https://github.com/T-Crypt/replicator.git && cd replicator
python -m venv .venv && . .venv/bin/activate
pip install -e ".[all]"            # the app, MCP server, STEP/IGES import and tests
pytest -q                          # about 200 tests, under 30 s
replicator fixtures/rocket_engine.json
```

The extras are separate if you want less: `.[app]` for the window, `.[mcp]` for agents, `.[cad]` for
STEP and IGES import, `.[dev]` for tests. The core alone (`pip install -e .`) builds, checks and
exports programs headless: `python -m tools.check fixtures/house_two_bed.json`.

Optional tools: `blender` 4.x or 5.x on `PATH` for Cycles stills, the Blender round trip and FBX, USD
or .blend import.

### Models

Specifying, editing by sentence, naming parts and explaining need an OpenAI-compatible chat
endpoint. Nothing else does. The built-in `local` engine reads three environment variables:

| Variable | Default | Example |
|---|---|---|
| `REPLICATOR_LLM_URL` | `http://127.0.0.1:8080/v1` (llama.cpp server) | `http://127.0.0.1:11434/v1` (Ollama), `http://127.0.0.1:1234/v1` (LM Studio) |
| `REPLICATOR_LLM_MODEL` | `local` | `qwen3:32b` |
| `REPLICATOR_LLM_KEY` | unset | a bearer token, if your server wants one |

Bigger models write better programs; a 27B to 32B coder model is a good start, and `tools.bench`
measures how well yours does. To name more engines, add them to `services.json` (in
`~/.config/Replicator/` on Linux, or wherever `$REPLICATOR_SERVICES` points). The key itself stays in
the environment variable the entry names:

```json
{"default_engine": "lab-ft",
 "endpoints": [{"name": "lab-ft", "url": "http://192.168.1.40:8000/v1", "model": "cad-ft-7b"},
               {"name": "hosted", "url": "https://api.example.com/v1", "model": "big", "key_env": "EXAMPLE_KEY"}]}
```

Engines appear in the picker in the header and in the MCP `specify` tool.

### GPU

The window draws with Qt Quick 3D on whatever GPU Qt picks. On a machine with an Intel iGPU and an
NVIDIA card, Replicator draws on the iGPU, so the card's memory stays free for a local model.
`REPLICATOR_GPU=any` turns that off and `REPLICATOR_GPU=igpu` forces it. `--software` draws on the
CPU with Mesa's llvmpipe.

### Headless frames

Qt's `offscreen` platform can't run Qt Quick 3D, so `--shot` loads the window hidden and grabs a frame:

```sh
python -m replicator.app fixtures/turbofan.json --software --shot out/build.png
python -m replicator.app fixtures/turbofan.json --software --shot out/x.png --mode dissect --explode 0.9
```

`--step N`, `--blueprint 0..1`, `--select ID` and `--size WxH` set up the frame. The README previews
come from these commands.

## The BuildProgram

Every view edits one JSON document. Ops run in order; placement (`translate`, `rotate`, `scale`)
applies last. Coordinates are Y-up and right-handed, in the program's `units`.

```json
{
  "version": 1, "name": "Vector engine", "units": "mm",
  "materials": {"steel": {"base_color": [0.6, 0.62, 0.65], "metalness": 1.0, "roughness": 0.35}},
  "ops": [
    {"id": "nacelle", "op": "revolve", "label": "Nacelle", "component": "Intake Cowl",
     "params": {"points": [[60, 0], [64, 0], [62, 180], [58, 180]]}, "material": "steel"},
    {"id": "blade", "op": "box", "label": "Fan blade", "component": "Fan Blade Set",
     "params": {"size": [4, 40, 14]}, "translate": [0, 30, 20]},
    {"id": "fan", "op": "array", "input": "blade", "label": "Fan, 18 blades", "component": "Fan Blade Set",
     "params": {"mode": "radial", "count": 18, "axis": "z"}}
  ]
}
```

A saved program lives in a `<name>.replicator/` folder: `program.json` plus `history/NNNN.json`, one
file per version, so an edit can be undone across sessions.

## Printing (optional)

Most of Replicator never touches a printer. When you do print, it treats the bed as a hard limit and
replicas as normal work:

- **Printer profiles.** A catalog of Bambu Lab beds (published sizes) or any custom bed, saved in
  `services.json`, with one active printer shown in the status bar. No active printer means no gate:
  every export works as before.
- **Never bigger than the bed.** STL and 3MF export to the active printer is refused when the build
  does not fit, naming each axis and the millimetres over, and the scale that would fit. Nothing is
  ever clipped.
- **Fit, orient and scale.** Fit check, orient to fit, scale to fit and replica presets (1:1, 1:N,
  fit to bed, target height). A scaled replica scales its plan too, so its checks still pass.
- **Agents.** MCP `printers`, `fit_check` and `scale_for_printer`.

Slicing and sending to a printer over the network are on the [roadmap](#roadmap).

## Image to 3D

Some shapes don't come from a list of operations: characters, creatures, anything organic. For
those, *File > Image to 3D* turns a picture (or a multi-view character sheet) into a mesh through a
ComfyUI you run with the Hunyuan3D 2.x models, cleans it, scales it to millimetres and opens it in
Reverse. Point it at your ComfyUI with `COMFY_URL` (default `http://127.0.0.1:8188`). Replicator never
loads an image model itself.

## Blender

Render > *Open in Blender* sends the current build to Blender 5.x through a vendored copy of the
[mcp-for-blender](vendor/mcp-for-blender) add-on (pinned, update check off, telemetry off, listening
on `localhost:9876` only). Sculpt or texture it there, then *Pull back from Blender* brings the
result into Reverse. The same server can be driven from an agent harness as an MCP tool.

## Project layout

```
replicator/
  core/program.py       BuildProgram schema, validation, JSON Patch, versions
  core/evaluate.py      manifold3d evaluator with per-op cache and step views
  core/ops_advanced.py  loft, pipe, helix, gear, deform
  core/assembly.py      components and exploded-view axes
  core/reverse.py       mesh analysis and the evidence ledger
  core/render.py        Cycles stills through blender --background
  core/step.py          STEP export: faceted B-rep solids with voids
  core/drawing.py       A3 drawing sheets: views, section or floor plan, dimensions, parts list
  core/critique.py      the nine engineering checks
  mcp_server.py         the workshop as MCP tools for agents
  core/blender_link.py  the mcp-for-blender round trip
  llm/                  specify, repair, edit, explain and name-parts prompts; built-in and configured engines
  knowledge/            curated engineering cards picked into the prompts by keyword
  qt/                   QML bridge, mesh geometry, procedural studio HDRI
  gpu.py                picks the GPU the window draws on (REPLICATOR_GPU)
  core/printers.py, core/fit.py  printer profiles, fit, orient and scale to the bed
qml/  shaders/          the workspace, the materialize and blueprint shaders
fixtures/               sample programs: engines, a PC, a Pi 5, a drone, a house
tools/                  check, sheet, showcase stills, record (preview films), readme_art
tools/readme_art.py     draws the README artwork
```

## Roadmap

- [x] Text to blueprint to program, step-by-step build, edit by sentence
- [x] Dissect, Reverse and Showcase modes; Blender round trip; image to 3D through ComfyUI
- [x] Drawing sheets: views, a section or floor plan, dimensions and a parts list from the program
- [x] STEP export, an MCP server for agents, endpoints you configure
- [x] Benchmark v0 and corpus export: seeded tasks scored by measuring the solid
- [x] Printer profiles, never-exceed gating, fit, orient and scale to the bed
- [ ] Scale-aware printability: features too thin at replica scale, and a thicken edit
- [ ] Slicing and send to printer, a print queue
- [ ] Reverse to program: imported pieces become real ops, each tied to its ledger entry
- [ ] Joints and mates as program data; URDF and MJCF with inertias from the exact solid
- [ ] A floor plan becomes rooms; sculpting and a node editor

The longer plan is in [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/REQUIREMENTS-workbench.md](docs/REQUIREMENTS-workbench.md).


## What Replicator never does

- **Never calls a model you did not name.** Every specify, repair, edit and label goes to the
  `local` engine or an endpoint you added yourself. Research (Wikipedia, or your own SearXNG) is off
  until you turn it on, and sends only search words.
- **Never loads a model in its own process.** Models run in your server; image to 3D runs in your
  ComfyUI; Cycles renders on the CPU with CUDA hidden.
- **Never runs anything from an imported file.** Archives unpack into a new folder with path, size
  and count checks.
- **Never replaces your program behind your back.** An edit that fails validation is dropped, and
  the last good version stays on screen.

## Contributing

Read [AGENTS.md](AGENTS.md): it is the map of the code, the invariants and how to extend each table
(an op, a check, a knowledge card, a material, an import format). Run `pytest -q` and
`python -m tools.check` on any program you touch. Licensed under [MIT](LICENSE).
