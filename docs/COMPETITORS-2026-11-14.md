# Replicator: competitor teardown and lane strategy

Written 2026-11-14. Source-level review, not a re-summarisation of READMEs.

Method: cloned each project at its default branch on 2026-11-14 into
`~/projects/replicator-research/competitors/` and read the kernel boundary, the agent/tool
layer, the intermediate representation and the verification code. Replicator claims come from
this checkout at `8e9c575` plus the 18 modified and 7 untracked files in the working tree.
Star counts and dates are from the GitHub API the same day. Where a claim is a guess, it says so.

## Status, end of 2026-11-14

Shipped the same day, after this teardown was written (commit after `2346b94`):

| Roadmap line | State | Proof |
|---|---|---|
| P0 film and README art | done | `brag-output/brag.mp4` (50.5 s, scored), `assets/build-timeline.gif`, `assets/range.jpg` |
| P0 MCP server | done | `replicator/mcp_server.py`, 10 tools; driven end to end over stdio by the SDK client; a rejected patch leaves the file byte-identical; an open window reloads agent edits as one undo step |
| P0 model endpoints | done | `endpoints` in `services.json`, key from an env var; live call through a configured endpoint to Strata |
| P0 STEP export | done | `core/step.py`; all 11 fixtures read back by OCCT `STEPControl_Reader` as valid solids (BRepCheck), volume within 4e-7 |
| P1 corpus export | done | `tools/corpus.py export/verify`; one row per program (prompt, program, geometry digest, mass, verdict, kernel); two exports of the fixtures are byte-identical and all 11 rows re-verify; a tampered row is caught. `client.dream` now stamps `source` (prompt, engine, date) |
| P1 benchmark v0 | done | `bench/` + `tools/bench.py`: four seeded tasks (flange, board, house, lamp; machine, electronics, building, everyday), registry of measured assertions, gate then 0.7 assertions + 0.3 checks; scoring is pure and re-scores identically; first live row: the local `agent` engine scored 1.000 on flange seed 13. Leaderboard publishing is next |
| P1 print lane | next, Bambu first | Operator direction 2026-11-14: build for a Bambu Lab printer first (arriving), then other printers; most prints are scaled replicas, so printer envelopes, never-exceed gating, scale and orient to fit, scale-aware printability, send to printer over LAN, a print queue, an off-by-default tailnet PWA and agent print tools. Requirements FR-PR-12 to 19, FR-PWA-1 to 3, FR-AG-P1 to 3 in `docs/REQUIREMENTS-workbench.md` 5.9a |

So the scorecard rows "MCP server", "STEP export" and "Runs your own model endpoint" now read **Y** for
Replicator. The remaining table stakes are the print answer, an install for a normal person, and
assemblies as data.

## Scope and positioning (operator, 2026-11-14)

Replicator is not a CAD workshop and must not be described as one. It builds just about everything:
house design and floor plans, technology and electronics, household and everyday items, advanced
engineering, concepts, and research-grounded builds. It is an engineer's tool first and a research
tool second, and it is multi-use. Each lane below has to be refined until it beats the nearest
competitor on a stated bar, not merely exist. Every competitor in this document owns one slice
(nurb: printable parts; Chili3D: feature-tree CAD; text-to-cad: agent plugins; CADAM: hobby
OpenSCAD; MAC: assembly research; sand3d: compact programs). None spans buildings, boards, machines
and concepts in one document with one set of checks.

| Lane | Nearest rival | The bar Replicator has to clear |
|---|---|---|
| L1 program as data | sand3d (compact programs, HF datasets) | Every program re-verifies headlessly in about a second with no Blender; the corpus publishes prompt, program, verdict, mass and build hash, and every row re-verifies from its hash |
| L2 open benchmark | nurb-benchmarks | Scores any endpoint (local, lab, hosted) on construction, repair and reverse, not just printability; same seed gives the same score to the digit; tasks span a house, a board, a machine and an everyday object |
| L3 reverse with a ledger | nobody (MAC goes the other way) | An imported model becomes an editable program whose rebuild is within a stated tolerance, every op tied to its ledger entry, unknowns listed |
| L4 construction as visual language | Chili3D (undo stack), nurb (live view) | Every README, film and benchmark row shows the build assembling and coming apart; Present narrates by component |
| L5 program to simulator | MAC, sand3d (URDF) | URDF and MJCF with inertias measured from the exact solid, joints as program data, one published MuJoCo scene |
| L6 breadth with one set of checks | none of the six | Houses, boards, household objects, machines and concepts all pass the same nine checks and produce the same sheet, STEP and report; buildings get floor plans, boards get real-scale parts, machines get formula-driven ops |

L6 is new: it is the operator's scope, and no competitor attempts it. Its first evidence is
`fixtures/house_two_bed.json`, specified by Strata from one sentence. Its first finding is a gap: the
model rotated the roof the wrong way (a V instead of a gable, 5.9 m tall against a planned 4.6 m),
and the checks passed it. Fixed the same day: a `roof` check for buildings (the roof covers the walls,
is not a V where a pitch is planned, does not cut into the rooms, matches a stated pitch) and a tiered
`size` check (warn past 15%, sent back to the model past 40%). The original roof is now blocked; the
desk lamp from the same run (twice its planned size) is blocked too. The tighter size check also
caught a defect that had shipped in the README turbofan since session 1: its fan, reverse vanes and
turbine were arrayed around the wrong axis (54% too wide); corrected, with fresh previews. Then
three more checks: radial arrays must spin about the round body they wrap (catches three of the
four broken turbofan rings), a part the plan puts "along" another must point the same way (the
lamp's springs), and knowledge cards can bound a part's elevation (the lamp's arms, which follow a
flat plan and so pass every build-against-plan check). Fixing a silent skip in `array_copies` then
caught the turbofan's fan blades fused into a flat disc. Breadth is real only when the checks hold for
every kind of thing.

---

## 1. What Replicator is, verified

| Fact | Evidence |
|---|---|
| Kernel is Manifold3D, exact solids, plus trimesh for imported meshes | 7 `from manifold3d` imports in `replicator/core/`, 5 `import trimesh`; no OCCT, no build123d |
| Document is JSON: `{"version", "name", "units", "materials", "blueprint", "ops": [...]}` | `replicator/core/program.py` docstring and `VERSION = 1` |
| Op vocabulary is a typed table the prompt is generated from | `PRIMITIVES`, `MODIFIERS`, `COMBINERS`, `PLACEMENT` in `program.py`; `PRIMITIVES` in `ops_engineering.py` (tube, nozzle, rotor, grille, wing) and `ops_advanced.py` (loft, pipe, helix, gear, deform) |
| About 24 ops total | 8 primitives + 5 modifiers + 3 combiners + 5 engineering + 5 advanced, minus overlap |
| Edits are JSON-Patch on the program | `import jsonpatch` in `program.py`, `client.py` repair round |
| Build step k is `ops[0..k]`; a consumed input hides from step k on | `program.py` docstring; timeline in `qml/` |
| Models are local: llama-swap `:9090` (dirk, coder, agent) and Strata `:8080`; the module states nothing goes to a cloud model | `replicator/llm/client.py` `ENGINES` |
| Nine automatic engineering checks | `CHECKS` in `core/critique.py`: floating, cavity_floating, overlaps, array_copies, thin_wall, off_axis, size, missing, stability |
| Mass, centre of gravity, principal inertia, does-it-stand | `core/physics.py` |
| Engineering drawing sheet out of the program: third-angle views, section A-A, dimensions, numbered callouts, parts list with computed masses, A3 title block, SVG and PNG | `core/drawing.py`, `tools/sheet.py` |
| Reverse mode tags every claim `observed`, `inferred` or `unknown`, with evidence and confidence | `core/reverse.py` `ledger_entry` |
| Imports ~30 formats, STEP/IGES through cascadio (OCCT compiled), FBX/USD/ABC/.blend through headless Blender | `core/importers.py` `ROUTES` |
| Exports glb, obj, stl, 3mf. No STEP export | `core/export.py` `FORMATS` |
| Blender round trip through vendored mcp-for-blender on `localhost:9876` | `core/blender_link.py` |
| No MCP server for Replicator itself | Only hits for "mcp" are the Blender add-on |
| Size: ~9.4K lines of Python including tools and tests, 4.0K lines of QML in 34 files | `wc -l` over `replicator/`, `tools/`, `tests/`, `qml/` |
| Knowledge cards for 8 domains, 6 prompts, 10 fixtures | `replicator/knowledge/`, `llm/prompts/`, `fixtures/` |

Two things matter for everything below. First, the document is **data**, and the schema is the
source of the model's prompt. Second, the whole project is small enough that one person can hold
it: about 13K lines against the six competitors, which run from 18K to several hundred thousand.

---

## 2. The six, read at source level

### nurb (Shpigford) — the one to take seriously

★638, created 2026-07-25, pushed 2026-11-15 (active as of today), 12 contributors, 30 releases,
108 test files, 2 CI workflows, licence `NOASSERTION` (custom). macOS app today; Windows and
Linux announced.

- **Kernel:** build123d on OCCT. Exact B-rep, real fillets and chamfers, STEP export.
- **Agent layer:** an MCP server (`engine/src/nurb/mcp_server.py`, 1448 lines) that Claude Code,
  Codex, Gemini, Cursor or Grok connect to on the user's own subscription, plus Tauri desktop with
  an ACP bridge (`desktop/src-tauri/src/acp.rs`). Building tools are `write_part_source`,
  `edit_part_source`, `write_shared_source`, `edit_shared_source`, `run_build`.
- **IR:** a **Python source file** per part, edited as text by the agent, plus `measurements.toml`.
- **Verification is the product.** Thirteen printability rules run against the exact solid
  (`checks.py`, 1824 lines), and findings pin to the faces that fired them. Print time and grams
  come from driving the user's own OrcaSlicer or Bambu Studio (`slicing.py`, 768 lines). Exports
  3MF with the print settings the checks justify; STL, STEP and GLB beside it.
- **Provenance doctrine:** dimensions are recorded with how they were measured; a guessed number
  must be marked as a guess and stays marked until someone uses a caliper.
- **nurb-benchmarks** (separate repo, ★0 but serious): 6 tasks (`bit_block`, `bundle_holder`,
  `cable_clip`, `leg_cup`, `pole_rest`, `valve_knob`), gate-then-grade scoring, weights 0.3
  printability / 0.5 dimensional assertions / 0.2 flex probes that rebuild the part at another
  parameter and catch hardcoded dimensions. Candidate code builds in an isolated worker and only
  crosses back as B-rep geometry, so a forged pass scores zero. Rows are keyed by harness, model
  and effort, pooled across submissions.

What to steal: the measurement provenance rule, the face-pinned findings, print time and cost from
a real slicer, and the benchmark format (gates first, flex probes last, isolated candidate code).

What it cannot do: run a model you host yourself (the agent is a cloud CLI), take a mesh apart,
show you the construction as ordered steps you can stop and edit at step k, or produce a drawing.
Because the IR is code, its own benchmark needs flex probes to catch dimensions the model hardcoded
into literals; a schema with declared params does not have that failure mode.

### Chili3D (xiangechen) — the CAD architecture to study

★4991, created 2022-12-31, AGPL-3.0, 16 contributors, 10 releases, 628 test files.

- **Kernel:** OpenCascade compiled to WebAssembly, rendered through Three.js, in the browser.
- **Architecture:** a monorepo with `core`, `element`, `parametric`, `builder`, `storage` and `ai`
  packages. One document, one selection model, one undo stack shared by hand commands and the
  assistant. `run_program` applies modelling calls (one call is one undo step); `run_parametric`
  builds a parametric feature tree the user keeps editing.
- **Assistant:** runs in the browser against your key (Anthropic API, OpenAI Completions, OpenAI
  Responses, configurable base URL). Reads the tree, the geometry and the selection, captures
  viewport screenshots, loads guidance skills on demand, and compacts old turns into a journal.
- `chili3d-mcp` exists but is one contributor, one commit, zero tests. Agent-driving is a side
  project there, not the mainline.

What to steal: on-demand skill loading to keep the prompt small, conversation journaling instead of
truncation, and the idea that the assistant and the user commands must write through the same undo
stack.

What it cannot do: verify a part for printing, reverse a mesh into a program, generate a drawing,
or run without a browser and a cloud key. AGPL is real friction for a company that wants to embed
it.

### text-to-cad (earthtojake) — the ecosystem play

★26329, created 2026-04-22, MIT, 25 contributors, 30 releases, 7 CI workflows, 623 test files.

- **Kernel:** build123d (720 import sites).
- **Shape of it:** not an app. Plugins for Claude Code, Codex, Cursor and Grok, a `cad` MCP server,
  and a long-running `cad-server` daemon with a model registry, memoised kernel calls
  (`engine/kernel/memo.py`, 4960 lines), geometry tracing, `document.py` and `mechanism.py`.
  One installer script registers it into every agent app on the machine.
- **Engineering depth nobody else has:** DFM modules for CNC (3023 lines), moulding (2862) and
  sheet metal (2322), a finite-element package (`_internal/fea/` with `solve.py`, `mesh.py`,
  `materials.py`, `outputs.py`), drawings, electronics and KiCad entry points, and
  `robot_payload` for robotics.
- **Corpus:** `models/` carries f14d, falcon_heavy, tendon_hand, hypercar, mujoco scenes and
  assemblies, all as Python source.

What to steal: the daemon with a memoised kernel and a model registry, DFM rule sets per process,
and the one-command installer that lands in whatever agent the user already runs.

What it cannot do: it has no window. Everything the user sees belongs to someone else's agent app,
so there is no viewport, no timeline, no material story, no product. It has no path to a model the
user runs, because the "AI" is the host coding agent. Verification is library code the agent may or
may not call.

### CADAM (Adam-CAD) — the reach benchmark

★5428, created 2025-09-01, GPL-3.0, 10 contributors, 4 releases, last pushed 2026-10-15, about 18K
lines of TypeScript, 5 test files, no CI.

- **Kernel:** OpenSCAD compiled to WebAssembly, with manifold references.
- **Stack:** React 19 with a Supabase backend, so accounts, saved projects and a hosted deployment
  come free. Interactive dimension controls parse parameters out of the generated OpenSCAD
  (`shared/parseParameters.ts`). Cloud providers: Anthropic most, then Gemini and OpenAI.
- **Print awareness:** `meshPrintProcessUtils.ts` (1291 lines) on the mesh, after generation.

CADAM is the weakest engineering of the six and the easiest to use. It wins the hobbyist conversation
today with no benchmark, no CI and five tests. That is a warning about distribution, not about code.

What to steal: a hosted deployment with accounts, and dimension controls that a non-engineer can
drag without seeing the source.

### Multi-Agent-CAD (Tsinghua, IEI Lab) — the assembly research

★1081, created 2026-07-30, MIT, 2 contributors, ~75 commits in the last year, 2 releases, 15 test
files.

- **Pipeline:** decompose a brief into components, generate each with build123d, then
  `assembly_codegen` + `graph_assembly` + `selector_resolver`, then QA in `_qa_collision`,
  `_qa_mates`, `_qa_dimensions`, `_qa_kinematics` and `_qa_anchors`, plus an independent Judge and
  visual verification. Exports STEP, STL, GLB and **URDF** for simulation.
- Honest README: the gallery is curated output, "not a measured prompt-success rate".

What to steal: mate and kinematics QA as named checks, the independent judge that is not the
generator, and URDF out.

What it cannot do: it is research code. Conda-only install, two maintainers, no interactive
document, no timeline, no undo, no user.

### sand3d (Sandflow AI) — the representation rival, and the fastest riser

★1999 in eleven days (created 2026-11-03), Apache-2.0, 7 contributors, 3 releases, 48 test files,
3 CI workflows.

- **Idea:** write objects as short Python programs over Blender's `bpy` so a model emits a few
  hundred tokens and a person can read them. Modules: `_core`, `_guard`, `assembly`, `edit`,
  `frames`, `joints`, `materials`, `meshfile`, `ifcfile`, `urdf`, `parts`.
- **Joints are real:** `joints.py` models a parent, an axis, a range and a `follows` relation, so
  assemblies articulate.
- **Exports:** GLB, STL, URDF, IFC.
- **Datasets on Hugging Face:** `sand3d-objaverse` and `sand3d-cad`, public objects rebuilt as
  programs, plus an Explorer space.

What to steal: the compactness target (a program a model writes in a few hundred tokens), joint
semantics with ranges and follow relations, and publishing the corpus as a dataset.

What it cannot do: the kernel is Blender mesh, so there are no exact solids, no STEP, no fillet
guarantees, no print verification. No viewport application, and it needs Blender.

---

## 3. Scorecard

Verified from source. Y means the code path exists today; P means partial.

| | Replicator | nurb | Chili3D | text-to-cad | CADAM | MAC | sand3d |
|---|---|---|---|---|---|---|---|
| Exact solid kernel | Y Manifold | Y OCCT | Y OCCT/WASM | Y OCCT | P OpenSCAD | Y OCCT | N bpy mesh |
| IR is data (validated schema) | **Y** | N Python src | N calls | N Python src | N OpenSCAD | N Python src | N Python src |
| Schema-constrained generation | **Y** | N | N | N | N | N | N |
| Step-by-step construction you can stop and edit | **Y** | N | P undo | N | N | N | N |
| Reverse mesh to parts/ledger | **Y** | N | N | N | N | N | N |
| Evidence tags observed/inferred/unknown | **Y** | P measured vs guess | N | N | N | P judge | N |
| Engineering drawing sheet | **Y** | N | N | P | N | N | N |
| MCP server so any agent can drive it | **N** | Y | P | Y | N | N | N |
| Print checks against the solid | P 9 rules | Y 13 + faces | N | Y DFM by process | P mesh | P collision | N |
| Print time and cost | N | Y slicer | N | N | N | N | N |
| STEP export | **N** | Y | Y | Y | N | Y | N |
| Assemblies with joints | P explode only | P | Y tree | Y | N | Y + URDF | Y + URDF |
| Runs your own model endpoint | Y, local only | N | P cloud keys | N | N | P | N |
| Own window and viewport | Y Qt 3D | Y Tauri | Y browser | **N** | Y web | N | N |
| Install for a normal person | **N** launch.sh | Y dmg | Y URL | Y script | Y URL | N conda | P pip |
| Public benchmark | **N** | Y cloud only | N | N | N | N | N |
| Training corpus published | N | N | N | P models dir | N | N | Y HF |
| Lines of code (approx, own code) | 13K | ~26K py + Rust + TS | ~100K+ TS | ~400K py | 18K TS | ~30K py | ~15K py |
| Licence | private | custom | AGPL | MIT | GPL-3 | MIT | Apache-2 |

Three cells in that table are the strategy: Replicator is the only one with a data IR and
schema-constrained generation, the only one with a construction timeline and evidence-tagged
reverse, and the only one of that group with no MCP server, no STEP export, no benchmark and no
install story.

---

## 4. Corrections to the ChatGPT review

The review is directionally right and worth keeping. Four things need correcting.

1. **"Your biggest technical weakness is the geometry kernel."** Too strong. Manifold gives exact,
   watertight solids and boolean ops at 10 to 60 ms per build, which is the whole reason a local
   27B model can iterate. The real kernel gaps are narrow and named in `AGENTS.md`: `round` erodes
   then regrows so features thinner than twice its radius vanish, there are no persistent face and
   edge references, and STEP is import-only. Those justify an OCCT-backed *layer* for STEP-native
   exchange and fillet-critical features. They do not justify a rewrite, and cascadio already puts
   OCCT in the dependency tree for import, so the experiment is cheap.
2. **It missed nurb's benchmark and provenance doctrine.** That is the closest thing to a
   methodological competitor here, and it is where nurb's real moat is, not in OCCT.
3. **It missed the deployment gap.** Replicator needs `launch.sh`, PySide6, Qt Quick 3D and a
   llama-swap box. nurb ships a dmg, CADAM and Chili3D are a URL, text-to-cad is a curl one-liner.
   A moat nobody can install is a hobby.
4. **"Local LLM" listed as a differentiator.** The reviewer and the README both treat local-only as
   the selling point. It should be relaxed to "any OpenAI-compatible endpoint you name" (llama-swap,
   vLLM, Ollama, a lab's fine-tune, or a hosted API). Today `client.py` refuses a cloud model, which
   cuts off the two audiences we most want: a lab with their own served checkpoint, and a printer
   owner with no GPU. Self-hosted or hosted, on-prem or in the cloud, should be a config line, not a
   moral position, and it should stay that simple.

---

## 5. Lanes nobody holds

Checked against all six. Each entry says who is closest, and what breaks if we move.

### L1. Program-as-data: the verifiable engineering document

Every competitor's intermediate representation is executable code the model writes as text: Python
for nurb, text-to-cad, MAC and sand3d, OpenSCAD for CADAM, tool calls for Chili3D. Replicator's is
validated JSON with declared params, a per-op component, a material, and JSON-Patch edits.

Why nobody else can follow quickly: switching to a data IR means rewriting the kernel interface, the
timeline and every example. Code-as-IR is the easy path for an agent and the hard path for trust.

What it uniquely buys:
- **Nothing to game.** A dimension cannot be a literal, so a parameter is either declared or the
  build fails. nurb needs flex probes to catch what a schema already prevents.
- **Diff, merge and review.** A program diff is reviewable by an engineer; a Python diff is not.
- **Corpus.** Every dream run produces a `(prompt, blueprint, program, built solid, critique
  verdict)` tuple that a machine can re-verify. That is the artifact a lab fine-tunes on. sand3d
  publishes programs to Hugging Face but cannot re-verify one without a Blender session; Replicator
  verifies one headlessly in about a second through `tools/check.py`.

First step: a `corpus` export that walks a directory of programs and writes one JSONL row each with
the prompt, the program, the critique verdict, mass, and a build hash. Two days.

### L2. An open benchmark for construction, where any endpoint can be scored

nurb-benchmarks measures cloud agent CLIs on printability of B-rep code. Nothing measures local and
open models on *construction*, and nothing measures the timeline, the repair loop, or reverse.
Replicator already has the parts: `tools/check.py`, `tools/golden.py`, nine critique checks, ten
fixtures, and a headless shot path.

Own it by publishing three things: a task set (spec, function and judgment classes, copying nurb's
good idea of a deliberately missing dimension), a deterministic scorer that runs the program and
grades the solid, and a leaderboard that takes a base URL and a model name so a lab can score their
fine-tune against a 27B quantised model against a hosted frontier model. This is the cheapest way to
become the project a research team evaluates on, and it is the one a lab can add rows to without
asking anyone.

First step: port three of Replicator's fixtures into tasks with graded assertions, and add
`--endpoint` to the runner. Under a week.

### L3. Reverse with a ledger: from a stranger's mesh to an editable program

Reverse mode exists and is tagged `observed` / `inferred` / `unknown` with evidence and confidence,
and it finds pieces, patterns, contacts and assembly order. No competitor reconstructs a program
from geometry at all. MAC comes closest in the other direction: it generates parts then QA's the
assembly.

Why this is the one for industry: an incoming part with no drawings, a supplier's STEP that lost its
feature tree, a printed bracket you want to change by 2 mm. The ledger is what makes the answer
usable, because it says what was measured, what was inferred and what nobody can tell you.
nurb's `measured()` doctrine is the same instinct, pointed at forward design.

First step: close the loop from pieces to ops, so a Reverse session emits a BuildProgram with the
`mesh` op replaced by real ops where the geometry supports it, and every generated claim carries its
ledger id. This is the biggest existing-code payoff in the list.

### L4. Construction as the visual language

Nobody else shows an object being assembled in order, pausable at any op, with the consumed inputs
hiding, an exploded Dissect view, and a Present mode that narrates chapters by component. Chili3D
has an undo stack, nurb has a live view of each edit. Neither can express "step 9 of 31, and this
part does not exist yet".

This is also the cheapest marketing asset in the whole document: the film already in `out/film/`
(`cut.py`, `film.mp4`, 50.5 seconds) is that story. The demo competitors can copy is a screenshot;
the demo nobody can copy is a build that assembles itself and can be taken apart at any step.

First step: nothing to build. Finish the film, then make the timeline the first thing every README
GIF and every benchmark row shows.

### L5. Program to simulator asset

`physics.py` already computes mass per component, centre of gravity and principal inertia about the
CG from the material table and the exact solid. MAC exports URDF; sand3d exports URDF and IFC;
text-to-cad has `mujoco` model dirs and `robot_payload`. What none of them do is hand the simulator
inertias measured from the exact geometry rather than assumed from a density and a bounding box.

Ownable slice: program plus joints (from Reverse contacts or declared assemblies) plus computed
inertia, out to URDF and MJCF, so an embodied-AI lab drops a Replicator object into MuJoCo or Isaac
and trusts the numbers.

First step: MJCF and URDF writers that consume `physics.Mass` and add joints as first-class
program data (which the Workbench requirements already ask for). Then one published example scene.

---

## 6. Table stakes, in the order they hurt

These are not lanes. Missing them is why a better product loses to an easier one.

1. **An MCP server.** nurb, text-to-cad and (barely) Chili3D all let any agent drive their document.
   Replicator's `qt/bridge.py` already exposes an action registry of slots and properties; wrapping
   it as MCP tools is a week, and it turns Claude Code, Codex and a lab's agent into users of the
   workshop instead of bystanders. Also register it in the homelab harness configs so it is used
   daily on this network.
2. **STEP export.** nurb, Chili3D, text-to-cad and MAC all export STEP. Replicator imports it. Any
   engineer's first question.
3. **Print answer, not geometry answer.** 3MF with settings that the checks justify, plus print time
   and grams from a real slicer, and findings pinned to the face that fired. `thin_wall`,
   `floating`, `stability` and `size` already exist as critique checks; they need to be reported as
   print consequences and tied to a slicer call.
4. **Install for a normal person.** One command, a packaged build, and a model endpoint the user
   pastes (their own, or a hosted one they pay for). `launch.sh` and a required llama-swap box is
   the difference between 26,329 stars and one operator.
5. **Assemblies as data.** Joints, mates and component relations in the program, not an explode
   vector computed at view time. MAC and sand3d both treat this as core; the Workbench requirements
   draft already asks for it.

---

## 7. Roadmap

Effort is in operator-days at the pace this repo moves, and each line names the check that proves
it. Ordered so the first month is defensible in public.

| # | Work | Why now | Effort | Check |
|---|---|---|---|---|
| P0 | Finish the film, ship README art from it | L4 is free differentiation | 0.5 | `out/film/film.mp4` plus a looped GIF in the README |
| P0 | MCP server over the bridge: read program, patch ops, run build, run checks, take a shot | Every rival has one; turns agents into users | 5 | `claude` and `omp` each build a bracket in Replicator; the timeline shows their edits |
| P0 | Model endpoints: one `services.json` line, any OpenAI-compatible base URL, key from the environment | Opens the lab fine-tune and the no-GPU hobbyist | 2 | One dream against llama-swap, one against a hosted endpoint, same fixture, both pass `tools/check.py` |
| P0 | STEP export | First question from any engineer | 2 | Round-trip a build through FreeCAD and diff the volumes |
| P1 | Print lane: 3MF with justified settings, face-pinned findings, print time and grams from a slicer | Table stakes with the printer owner | 8 | A printed bracket: no supports needed where the checks said clear, time within 15 percent of the slicer's |
| P1 | Benchmark v0: 3 tasks ported from fixtures, deterministic scorer, `--endpoint` runner, public leaderboard | Cheapest route to being the thing labs evaluate on | 6 | Three rows: a local 27B, a local A3B, a hosted model, same seed, same score twice |
| P1 | Corpus export: JSONL of prompt, program, verdict, mass, build hash | Feeds L2 and the labs; makes every dream an asset | 2 | 200 programs, every row re-verifies from the hash |
| P1 | Joints and mates as program data, with mate QA | Rivals have it, Workbench needs it, L5 depends on it | 10 | Quadcopter fixture with named joints; a mate check fails when a rotor passes through an arm |
| P1 | Reverse to program: pieces and patterns to real ops, claims tied to ledger ids | The unique lane, half-built | 15 | Import `~/Downloads/robot.glb`, get an editable program whose rebuild is within tolerance, with unknowns listed |
| P2 | OCCT layer for STEP-native exchange and fillet-critical features, behind a geometry abstraction | Fixes the named gaps without a rewrite | 12 | The `round`-erases-thin-features case builds correctly through the OCCT path |
| P2 | MJCF and URDF out with computed inertias, one published scene | L5, robotics labs | 5 | A MuJoCo sim of a Replicator arm that stands up and reports the same mass |
| P2 | Packaging: one-command install, packaged app, first-run endpoint picker | Distribution | 8 | A clean machine, 10 minutes from curl to a printed part |
| P2 | Hosted or on-prem deployment with saved projects | CADAM and Chili3D own the "just open a tab" conversation | 15 | A second person designs a part on their own machine with no setup |

## 8. What to decline

- **Do not chase OCCT as the headline kernel.** Manifold is why a 27B model iterates in 60 ms.
  Replace nothing; add a layer where B-rep actually pays.
- **Do not become an agent plugin.** text-to-cad has 26K stars for that and no window of its own.
  The window is the product; expose it to agents rather than dissolving into one.
- **Do not build a feature-tree CAD.** Chili3D has four years and 628 test files on that. A
  procedural op history plus a timeline is a different, defensible thing; the review's warning
  stands.
- **Do not treat air-gapped or enterprise-deployment stories as a selling point.** It runs wherever
  Python runs and talks to whatever endpoint you name. That is one config line, not a product tier,
  and dressing it up as one makes the ordinary install look complicated.
- **Do not publish a benchmark you cannot score twice to the same digit.** nurb's rows are keyed by
  harness, version and content revision. A leaderboard that drifts is worse than none.

## 9. One paragraph to repeat

Replicator is an engineering and research workshop that builds almost anything, from a house with
its floor plan to a circuit board, a household object, a rocket engine or a concept, and it is the
only one of its kind where the design is a **validated program instead of generated code**. That one fact buys three things none of the six have: construction you can watch,
stop and edit at any step; a reverse path that turns an unknown object into an editable program with
a ledger saying what was measured and what was guessed; and a corpus of machine-verifiable build
programs that any model endpoint can be scored on or fine-tuned from. Point it at a lab's served
checkpoint, a local 27B on a 4090, or a hosted model, and the same document, timeline and checks
work. The MCP server, STEP export and configurable endpoints shipped the same day; the gap left is a
print answer, an install a normal person can run, and checks that hold as well for a house or a lamp
as they do for an engine.
