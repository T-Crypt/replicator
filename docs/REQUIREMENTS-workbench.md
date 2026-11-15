# Replicator Workbench: requirements (draft 1, 2026-11-14)

Status: **draft for operator review.** Nothing here is built yet. It extends `docs/DESIGN.md` (roadmap item 3,
"3D printing") into a full workbench, and it keeps that document's three rules: one document, labelled evidence,
and the GPU belongs to the models.

## 1. What this adds

Replicator today dreams an object, builds it as a BuildProgram, and lets you take it apart, explain it and show it.
The Workbench makes the object **real**. It covers the whole path from an idea to a thing on the bench:

```
Concept -> Scaffold -> Design -> Engineer -> Source -> Fabricate -> Assemble -> Refine
 (what)     (where)     (shape)   (works?)   (buy/cost) (print...)   (steps)    (loop)
```

It is the destructible workshop table. Anything on the table can be broken into parts, and each part is something
you print, buy or make. A part can be saved to a library, reused in another build and scaled. The same table holds a
printed gadget, a robot arm with motors and wiring, a cosplay prop, an enclosure for a circuit board or a piece of
furniture. 3D printing is the first fabrication process. The model is built so that others (laser cutting, CNC,
woodworking, sheet metal) plug in the same way.

### Honest scope

This is a CAD, CAM, ECAD and PLM feature set. Commercial tools spend team-years on each one. The plan delivers it in
layers, and each layer is usable alone. These limits are known up front:

- **Simulation is estimates, not FEA.** Strength checks are textbook formulas (beam bending, wall stress, layer
  adhesion factors). They are labelled `computed (estimate)` and never "safe". Real FEA (CalculiX on the CPU) is a
  later option.
- **Prices go stale.** An offline catalog price carries its date and source. A live price needs the research lane
  (network), and only part numbers and search words leave the machine.
- **A 27B model does not know engineering.** Section 4 is the answer to that, and it shapes every other section.
- **Mains voltage, load-bearing, food-contact and child-safety uses are flagged, never certified.**

## 2. Principles (binding on every requirement)

| # | Principle | What it means in practice |
|---|---|---|
| P1 | One document | The BuildProgram grows into a **Project** (section 3). Every panel, checker and export is a view of it. Edits are JSON Patches, versioned in `history/`. |
| P2 | The model chooses, the code computes | The model picks a part, a joint type or a material from a list. Code works out every number: clearances, gear ratios, wire gauges, costs, print time. A number the model typed is `assumed` until a solver or a source backs it. |
| P3 | Every claim has a kind | `measured` (from geometry), `computed` (a solver, with its formula), `cited` (a source with date), `catalog` (a library entry), `assumed` (a model or user guess), `concept` (fiction). Shown in the UI as in Reverse and Explain. |
| P4 | Small asks | No model call does more than one job. "Design a robot arm" becomes many bounded calls, each with a schema, a short context and a checker. |
| P5 | Checkers close every loop | After each stage, deterministic checkers produce a list of issues. Issues go back to the model as repair input (as validation errors do today), up to a bounded number of rounds, and then to the user. |
| P6 | Local and private | Models on llama-swap or Strata. Slicers, solvers and Blender on the CPU with `CUDA_VISIBLE_DEVICES=`. Printers are reached on the tailnet only. Nothing is uploaded. |
| P7 | The user can always take the wheel | Every agent action is a proposal you can see as a diff. Parts can be locked. Manual edits are never overwritten by a later model edit. |

## 3. Data model: from BuildProgram to Project

The BuildProgram stays the geometry history. A project adds the layers it lacks. All of it lives in one folder,
`<name>.replicator/`, as JSON, and one JSON Patch can touch any layer.

| Layer | Holds | New or existing |
|---|---|---|
| `spec` | The requirements for the object: purpose, envelope, loads, environment, budget, quantity, target processes, printer profile, must-haves and must-nots | New |
| `params` | Named, typed variables with units and expressions (`wall = 2.4 mm`, `bolt_d = M3`, `arm_len = 3 * link`). Ops reference them as `"$wall"`. Scaling and variants are done by changing params | New, the foundation for everything else |
| `ops` | Geometry history, as today, plus new ops (section 5.4) | Existing |
| `parts` | Every physical part: id, the component it belongs to, `kind` (`printed`, `purchased`, `fabricated`, `salvaged`), process, material, quantity, its `library` source if any, lock state | Extends `component` |
| `interfaces` | Named datums and features where parts meet: bore, shaft, face, slot, screw boss, connector port, each with a frame (origin plus axis) | New |
| `joints` | How parts connect and move: `fixed`, `revolute`, `prismatic`, `screw`, `gear_mesh`, `belt`, `cam`, `spring`, with limits and drivers | New |
| `fasteners` | Screws, nuts, inserts, pins and magnets, each tied to an interface pair and a catalog entry | New |
| `electrical` | Components (catalog refs), pins, nets, power rails, connectors, the harness (wires with gauge, colour, length and route) | New |
| `bom` | A computed view: parts plus fasteners plus electrical plus consumables, with quantity, unit cost, its source and date, and totals at N units | New, computed (never typed by the model) |
| `fab` | Per-part fabrication plan: orientation, split, slicer profile, supports, plate layout, results (time and grams from the slicer) | New |
| `assembly` | Ordered steps: which parts, which fasteners, which tools, and a viewport camera for each step | Extends `assembly.py` |
| `ledger` | Every claim, with its kind and evidence | Extends Reverse's ledger |
| `issues` | Open checker findings, with severity, the part they concern and the fix proposed | New |

**FR-DM-1** A schema for each layer, generated from code as the op schema is today, so prompts and validation never
drift. **FR-DM-2** Old v1 programs load unchanged, and a migration lifts them to a project. **FR-DM-3** Units are
explicit on every number, and conversion lives in one place. **FR-DM-4** A part, an assembly or a whole project can
be exported as a **library item**: a sub-program with its own params, interfaces and BOM, which can be placed in
another project and stays parametric.

## 4. Working with 27B models that lack skills or world knowledge (cross-cutting, P0)

The target model is Dirk-27B, or any 20-35B local model. It reasons well enough on a small, well-posed task. It
lacks reliable recall of part numbers, standards, material properties, wire tables and mechanism design rules, and
it makes arithmetic slips. The system must still produce sound designs. Requirements:

**FR-AI-1 Knowledge cards, not recall.** A versioned knowledge base in the repo (`knowledge/`), curated by people and
tested in CI:
- Standards tables: ISO metric threads and clearance or tap holes, heat-set insert bores, bearing sizes (608, 6800
  series...), shaft and keyway sizes, belt pitches (GT2...), gear modules, AWG and mm² ampacity, connector families
  (JST-XH and PH, XT30/60, Dupont, Molex Micro-Fit), common MCU and driver pinouts.
- Process rules per process: FDM minimum walls, overhang angles, bridge lengths, hole shrinkage, fit clearances by
  material and nozzle (press, slip, running), layer-direction strength factors.
- Materials: PLA, PETG, ABS/ASA, TPU, PA-CF and resin, with density, glass transition temperature, rough strength,
  cost per kg, and food, UV and heat notes (each value cited).
- Mechanism recipes (FR-AI-3).
Each card is small (well under 1k tokens), has a stable id, and is retrieved by keyword and tag, not by embeddings on
the GPU. Any embedding runs on the CPU, and only after asking (CLAUDE.md rule).

**FR-AI-2 Retrieval per call.** Each model call gets only the cards for its task, picked by code from the spec, the
selected part and the stage. The prompt budget per call is set and enforced (target: under 6k tokens of context).

**FR-AI-3 Recipes: worked parametric templates.** Mechanisms the model can *choose and fill in* rather than invent:
hinge (pin, living, print-in-place), snap fit (cantilever, annular), threaded insert boss, screw boss, dovetail and
dowel split joints, bearing seat, shaft with D-flat, spur, planetary and worm gearbox, lead-screw linear axis, belt
axis, cam and follower, servo horn mount, NEMA 17 mount, battery box, cable gland, enclosure with lid and PCB
standoffs, wire channel. Each recipe is a library item (FR-DM-4) with params, interfaces, a BOM and its own tests.
The model's job is "which recipe, which params"; the recipe makes valid geometry.

**FR-AI-4 Constrained output.** Every call uses JSON-schema constrained decoding (llama.cpp `response_format` /
grammar) generated from the layer schemas. Enumerations (recipe ids, catalog ids, materials, joint types) are enums
in the schema, so the model cannot name a part that does not exist. The lenient parser stays as a fallback.

**FR-AI-5 Tools for maths.** The model never computes. It calls deterministic tools through a small tool interface
(or emits a request the pipeline resolves): `fit(d, class, material)`, `gear_pair(module, ratio)`,
`wire_gauge(current, length, drop)`, `screw_for(load, material)`, `print_cost(grams, hours)`, `beam_check(...)`.
Results come back as `computed` claims with the formula.

**FR-AI-6 Decomposition.** Each pipeline is a fixed sequence of small stages with a checker after each (section 5).
Stage outputs are saved, so a failure retries one stage, not the whole run.

**FR-AI-7 Knowing what it doesn't know.** A model answer can carry `unknown` with a question. The pipeline routes it
to (a) a knowledge card search, (b) the research lane if on, or (c) the user, as a short question in the studio. It
never fills the gap with an invented value marked as fact.

**FR-AI-8 Multiple choice before free text.** Where a design choice is open, code proposes 2 to 4 options from the
recipes and catalog, and the model ranks them with reasons. It is not asked to invent from nothing.

**FR-AI-9 Golden eval suite.** A set of reference tasks with pass criteria (for example "print-in-place hinge 40 mm",
"desk fan with a 5 V motor and a USB-C input", "two-axis camera gimbal with SG90 servos", "Raspberry Pi 5 case
with a 40 mm fan", "wall-mount bracket for 5 kg"), run per model and role, with the pass rate logged in
`state/evals/` style. A model or prompt change that lowers the pass rate does not ship.

**FR-AI-10 Learning from use (P2).** Accepted designs, accepted repairs and user corrections are stored as examples
(local only), usable as few-shot examples and later as fine-tune data in hf-lab.

**FR-AI-11 Graceful degradation.** If the model fails a stage after its repair rounds, the studio shows the best
valid state, the open issues, and the recipe or manual tool that would fix it. No stage blocks the user.

## 5. Functional requirements by stage

Priority: **P0** first usable release, **P1** next, **P2** later. Each requirement lists its acceptance check.

### 5.1 Concept creation

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-CO-1 | P0 | A **spec interview**: from one sentence, the model drafts the `spec` and asks at most 5 short questions for gaps that matter (size, load, power, budget, printer). Each answer is a patch to `spec` | The golden prompts each yield a valid spec with no more than 5 questions |
| FR-CO-2 | P0 | **Variants**: 2 to 4 concept directions (for example "belt drive" against "gear drive"), each a light blueprint with its trade-offs, side by side on the floor | Variants render together and one click promotes a variant to the project |
| FR-CO-3 | P1 | Concept from image or sketch: the Holodeck sheet or a photo goes to the `vision` role, which drafts the spec and scaffold; the existing image-to-3D lane supplies reference geometry | One image yields a scaffold that matches its proportions within 10 % |
| FR-CO-4 | P1 | Concept from salvage: start from an imported mesh or from library items ("build around this motor and this battery") | Placed library items become locked parts the design must fit |

### 5.2 Scaffold

The scaffold is the skeleton before detail: envelope, datums, part stubs and the interfaces between them. It is what
lets a weak model get layout right before it touches shape.

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-SC-1 | P0 | From the spec, generate a scaffold: bounding blocks per part, named interfaces, joints in their rough positions, purchased parts at their catalog dimensions | The scaffold builds, no stubs intersect (beyond declared joints), all purchased parts are real catalog entries |
| FR-SC-2 | P0 | Scaffold view: translucent blocks, interface glyphs (axis arrows, bore rings), joint symbols, the envelope cage from `spec` | Visible in the viewport and in `--shot` |
| FR-SC-3 | P0 | Each stub is then **detailed** one part at a time (5.3), with its interfaces fixed, so detailing one part cannot break its neighbours | Detailing a part never moves an interface without an explicit patch to `interfaces` |
| FR-SC-4 | P1 | Drag stubs and interfaces in the viewport; the gizmo snaps to interfaces and grid | Moves are patches, undoable |

### 5.3 Design Studio: live co-editing with the agent

The studio is where the user and the model work on the same project at the same time. Two ways to work, switchable at
any moment:

- **Stage mode** (per part, per stage): pick a part or component; the studio shows its pipeline (scaffold, shape,
  features, fit, fab), what each stage produced and its open issues. Run, re-run or edit one stage of one part.
- **Intuitive mode**: select anything and say or type what you want ("make this thicker", "add a cable hole here",
  "this needs to hold a 608 bearing"). Clicks in the viewport turn into references in the request (a face, a point,
  an interface).

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-ST-1 | P0 | **Selection-scoped requests**: the model gets the selection, its params, interfaces, neighbours and the relevant cards, not the whole project | Prompt context stays under the FR-AI-2 budget on the 22-step engine fixture |
| FR-ST-2 | P0 | **Live proposal preview**: a proposed patch shows as a ghost overlay (added in green, removed in red, changed in amber) and a readable diff list; accept all, accept per hunk, or reject | Accept and reject both leave a clean history; a rejected proposal leaves no trace |
| FR-ST-3 | P0 | **Locks**: lock a part, a param or an interface; the model's schema excludes locked paths, and the patch applier rejects them | A test patch on a locked path is refused with a message |
| FR-ST-4 | P0 | **Params panel**: named params with sliders and expressions; changes rebuild live (the kernel is already 10 to 60 ms) | Dragging a slider rebuilds at interactive rates on the engine fixture |
| FR-ST-5 | P0 | **Issues panel**: checker findings per part (printability, fit, interference, electrical, cost), each with "show me", "fix it" (asks the model for a patch scoped to that issue) and "ignore with reason" | Each golden task's issues can be cleared through the panel |
| FR-ST-6 | P1 | **Agent run view**: a live log of the stages being run, the cards retrieved, tool calls and their results, the claims made, with stop at any point | Stopping leaves the last valid state |
| FR-ST-7 | P1 | **Direct features**: click a face to add a hole, a boss, a fillet, a text label or a chamfer; the click writes the op, and the model is not needed | Each feature is one patch, editable afterwards in the Attribute Manager |
| FR-ST-8 | P1 | Voice: dictation (already in the bridge) feeds intuitive mode | A spoken edit applies as a typed one does |
| FR-ST-9 | P2 | Node view of the op and joint graph (DESIGN.md roadmap 4) | Same document, edits round-trip |

### 5.4 Geometry additions needed by the rest

| ID | Pri | Requirement |
|---|---|---|
| FR-GE-1 | P0 | `hole` op (through, blind, counterbore, countersink, tapped, insert), taking a standard size from the cards |
| FR-GE-2 | P0 | `fillet` and `chamfer` on edges or by angle (manifold3d with a Blender CPU worker fallback) |
| FR-GE-3 | P0 | `split` op: cut a part by a plane or a path, and add joining features (dowel pins, dovetail, tongue and groove, screw tabs, glue registration) |
| FR-GE-4 | P1 | `text` op (emboss, deboss) for labels and part ids |
| FR-GE-5 | P1 | `thread` op (real modelled threads for large printed threads; heat-set inserts are preferred below M6) |
| FR-GE-6 | P1 | Sketch op with constraints (2D profile with dimensions) for extrude and revolve, so profiles are parametric |

### 5.5 Breakdown

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-BD-1 | P0 | **Assembly tree**: project, then assemblies, then parts, then features, with kind icons (printed, purchased, fabricated) | Matches `parts` exactly |
| FR-BD-2 | P0 | **Exploded breakdown** per assembly (extends Dissect), with fasteners shown and numbered callouts matching the BOM | Callout numbers equal BOM line numbers |
| FR-BD-3 | P0 | **Assembly steps** generated from joints and fasteners (extends `disassembly_order`): each step lists parts, fasteners, tools and a camera; playable in Present mode | Every part appears in exactly one step; no step needs a part from a later step |
| FR-BD-4 | P1 | **Build sheet** export: PDF or HTML with BOM, cut list, print list, wiring diagram and step pictures | Opens offline, every image comes from `--shot` |
| FR-BD-5 | P1 | **Destructive mode**: break any imported or built object into salvageable parts and save them to the library; Reverse's piece analysis feeds it | A broken-out part placed in a new project keeps its interfaces |

### 5.6 Mechanics

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-ME-1 | P0 | **Joints** (section 3) with limits; the viewport can drive each joint with a slider | Driving a revolute joint moves its subtree |
| FR-ME-2 | P0 | **Interference and clearance check** across the joint range (sampled) and at rest, using manifold3d intersection | Reports colliding part pairs with the joint value where it happens |
| FR-ME-3 | P0 | **Fit classes**: an interface pair has a fit (press, slip, running, loose), and code applies the clearance for the process, material and nozzle from the cards | The hole size changes when the printer profile changes |
| FR-ME-4 | P1 | **Kinematic chains**: gear trains, belts and lead screws compute ratio, output speed and torque from the driver (motor catalog entry) | `computed` claims with formulas in the ledger |
| FR-ME-5 | P1 | **Motion playback**: animate the mechanism through its range in the viewport and in Present mode | Plays at viewport frame rate on the iGPU |
| FR-ME-6 | P1 | **Strength estimates**: wall stress, beam bending and screw pull-out, with layer-direction derating for FDM | Labelled `computed (estimate)`, with a safety factor shown, never "pass" for flagged uses |
| FR-ME-7 | P2 | FEA through CalculiX on the CPU for one selected part | Runs under 2 min on a bracket, results drawn as a heat map |

### 5.7 Wiring and electronics

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-EL-1 | P0 | **Electrical components from the catalog**: MCU boards, drivers, motors, servos, sensors, LEDs, switches, PSUs, batteries, connectors, each with its pins, voltage, current and physical model | A placed component has true outer dimensions and mounting holes |
| FR-EL-2 | P0 | **Netlist**: nets between pins; checks for unconnected required pins, voltage mismatch, rail over-current, reversed polarity on keyed connectors | Each check has a failing test case |
| FR-EL-3 | P0 | **Power budget**: sum of loads per rail against supply; battery runtime estimate | `computed` claims |
| FR-EL-4 | P0 | **Wire sizing**: gauge from current, length and allowed drop (AWG and mm² table in the cards); colour convention | Matches the table for a set of reference cases |
| FR-EL-5 | P1 | **Harness routing**: wires routed as `pipe` ops through channels and clips in printed parts; the length goes to the BOM | Routes avoid moving parts across the joint range |
| FR-EL-6 | P1 | **Wiring diagram** export (SVG): blocks, pins, nets, wire colours and gauges | Readable at A4 |
| FR-EL-7 | P1 | Enclosure recipes that place board standoffs, ports and vents from the component models | A Pi 5 case golden task passes the fit check |
| FR-EL-8 | P2 | KiCad export of the netlist (and schematic symbols where available) for a custom PCB | Opens in KiCad 9 |
| FR-EL-9 | P0 | **Safety flags**: anything over 50 V AC or 120 V DC, lithium packs without protection, or currents over 10 A raises a blocking notice that names the risk | Notice shown, and the build sheet carries it |

### 5.8 Sourcing, pricing and costs

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-SO-1 | P0 | **Offline catalog** (`catalog/`): purchased parts with specs, dimensions, interfaces, a typical price, a currency and the date that price was seen, plus vendor links | Every catalog price shows its date in the BOM |
| FR-SO-2 | P0 | **Match to spec**: given requirements (for example "bearing, 8 mm shaft, under 25 mm OD"), code filters the catalog and ranks candidates; the model only explains the trade-off | Returns a real entry or says none fit |
| FR-SO-3 | P0 | **Printed part cost**: grams and hours from the slicer (measured), filament cost per kg from the material card, electricity at a set rate and printer power, and an optional machine-wear rate | Matches a hand calculation for the reference print |
| FR-SO-4 | P0 | **BOM with totals**: per line and per project, at quantity 1 and at a chosen N, with consumables (filament, inserts, glue, heat-shrink) | The total equals the sum of its lines; each line has a claim kind |
| FR-SO-5 | P1 | **Live quotes** through the research lane (off by default): vendor search for a part number; the price is stored as `cited` with URL and date; only the part number and search words leave the machine | Turning research off leaves the catalog prices in place |
| FR-SO-6 | P1 | **Scaling**: change a scale param or the quantity; code re-checks fasteners and catalog parts that no longer fit (an M3 boss scaled 2x proposes M5 rather than an M6 hole with an M3 screw), re-slices, and shows cost per unit at 1, 10 and 100 with price breaks where known | A 2x scale of a golden task re-selects fasteners and passes fit |
| FR-SO-7 | P1 | **Make or buy**: for a part that could be printed or bought (gears, brackets, spacers), show both costs and times | Both options carried in the BOM, one active |
| FR-SO-8 | P2 | Vendor APIs that need keys (Digi-Key, Mouser, LCSC), with keys in an env file (mode 600), never in the repo | Off unless configured |

### 5.9 3D printing

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-PR-1 | P0 | **Printer profiles**: build volume, nozzle, materials loaded, firmware or host (Klipper/Moonraker, OctoPrint, Bambu LAN, or file only), slicer profile names | Profiles live outside the repo (services file, as voice does) |
| FR-PR-2 | P0 | **Printability check** per part: watertight (already guaranteed), overhangs past the profile angle, thin walls, small features under nozzle width, unsupported bridges, islands, fits that need a clearance, parts too large for the bed | Issues drawn on the mesh as a heat map and listed in Issues |
| FR-PR-3 | P0 | **Orientation**: score candidate orientations (support area, strength along the load path from joints, bed contact, height) and propose the best, with the reasons | The user can override; the score shows |
| FR-PR-4 | P0 | **Auto-split** parts that exceed the bed, using FR-GE-3 joins, placed away from load paths and visible faces where possible | Each piece fits the bed and the joins are in the BOM |
| FR-PR-5 | P0 | **Slice** with PrusaSlicer or OrcaSlicer CLI on the CPU; time, grams and support volume come back as `measured` | Runs headless with no GPU context (checked with `nvidia-smi`) |
| FR-PR-6 | P0 | **Export**: 3MF with part names, colours and per-part settings; STL per part; G-code from the slicer | 3MF opens in the chosen slicer with parts named |
| FR-PR-7 | P1 | **Plate packing**: lay out all printed parts across plates by material and colour | Plates fit the bed with margins |
| FR-PR-8 | P1 | **Send and watch**: upload and start on Moonraker or OctoPrint over the tailnet; show progress; the webcam frame if the host offers one | Never sent without a confirm click |
| FR-PR-9 | P1 | **Multi-material**: per-part and per-face material and colour mapped to filament slots | Shown in the 3MF |
| FR-PR-10 | P1 | **Tolerance test print**: generate a calibration coupon for the active printer and material; measured results update the fit clearances in the profile | The next fit uses the new clearance |
| FR-PR-11 | P2 | Resin printing profile (hollowing, drain holes, supports) | |

### 5.9a Printing direction (operator, 2026-11-14): Bambu Lab first, then other printers

Notes, not yet built. They extend FR-PR-1 to FR-PR-11 above and set their order.

**Target printer.** Build for a Bambu Lab printer first; other printers follow. The operator is buying one (model not
chosen yet). Until it arrives, code is written against Bambu's published profiles and LAN-mode behaviour, and the
file export path always works without a printer. Everything printer-specific sits behind the printer profile
(FR-PR-1), so Klipper/Moonraker, OctoPrint and Prusa printers become profiles plus a transport, not a rewrite.

Facts to verify on the device when it arrives (recalled, not measured): Bambu's LAN mode talks MQTT over TLS for
status and commands and takes files over FTPS, authorised by an access code shown on the printer; Bambu Studio and
OrcaSlicer both carry Bambu profiles and have a CLI. Published build volumes to confirm for the model bought: X1
Carbon, P1S, P1P and A1 256 x 256 x 256 mm; A1 mini 180 x 180 x 180 mm; H2D about 350 x 320 x 325 mm.

**Most prints are replicas.** A build is often printed at reduced scale, so fitting the printer is a first-class
function, not an error message.

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-PR-12 | P0 | **Printer envelope**: each printer profile carries its usable build volume (bed X and Y, height Z) minus a safety margin, the nozzle, and loaded filaments. Pick from a catalog of known printers (Bambu models first) or enter dimensions by hand; several printers can be saved and one is active | Profiles live outside the repo (services file); the active printer shows in the status bar |
| FR-PR-13 | P0 | **Never exceeds the bed**: every export for printing and every send is gated on the envelope. A part or plate that does not fit is refused with the overflow per axis, never silently clipped | A part 1 mm too tall is refused and the message names the axis and the millimetre |
| FR-PR-14 | P0 | **Fit functions**: fit check (per part and per plate, with clearance left on each axis); scale to fit (largest uniform scale that fits, shown as a factor and as final dimensions); replica presets (1:1, 1:N, fit to bed, fit to a target height); orient to fit (try the rotations that keep the part flat on the bed); split when even the best orientation does not fit (FR-PR-4) | Scale to fit on a 1.2 m house gives the exact factor, and the scaled build passes the fit check on the active printer |
| FR-PR-15 | P0 | **Scale-aware printability**: when a replica is scaled down, report the features that drop below the nozzle width or minimum wall (railings, pins, thin fins) and offer to thicken them to the printable minimum or drop them, as a separate edit | A 1:50 house lists the window mullions that vanish at 0.4 mm and the thicken edit makes them printable |
| FR-PR-16 | P0 | **Send to printer**: one action that fits, slices (Bambu Studio or OrcaSlicer CLI, CPU only), packages a printer-ready 3MF and sends it to the active printer over the LAN, with a confirm click every time. The access code lives in a mode 600 file referenced from config, never in a repo or a log | A print starts on the Bambu from Replicator after one confirm |
| FR-PR-17 | P0 | **Export for printing** without a printer: 3MF (named parts, colours, the plate), STL per part, STEP for CAD, and the sliced file when a slicer is present | Opens in Bambu Studio with parts named and inside the bed |
| FR-PR-18 | P1 | **Print queue and status**: queued, slicing, sending, printing (progress, layer, time left, camera frame where the printer offers one), done or failed; a job keeps its program version, scale and settings so it can be reprinted exactly | The queue survives an app restart |
| FR-PR-19 | P2 | **Replicator network print service**: a small tailnet-only service that holds the queue and talks to the printers, so a phone, the PWA or another machine can queue a print without the desktop app open | Not exposed beyond the tailnet |

**Small PWA, off by default.**

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-PWA-1 | P1 | A toggle in Preferences, off by default, that serves a small installable web app from the desktop app (or the print service) on the tailnet only, behind a token; nothing public | With the toggle off, no port is open |
| FR-PWA-2 | P1 | Read-only views: renders, projects, creations, build timelines (step through a build, using exported per-step frames or GLB), and the print queue with live status | A queued print shows its progress on the phone |
| FR-PWA-3 | P2 | Light actions from the phone: queue a print of an existing job, pause or cancel a running print (each with a confirm) | Never starts a print without a confirm |

**The local agent prints and assists.**

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-AG-P1 | P1 | MCP tools for printing: list printers and the active envelope, fit check, scale to fit, orient, split, slice, export for printing, queue, status | An agent fits and queues a part through MCP alone |
| FR-AG-P2 | P1 | Sending to a physical printer needs the operator's confirm in the app (or a per-printer auto-send switch the operator sets); the agent can prepare and queue, not start a print on its own by default | The confirm appears in the app and the PWA |
| FR-AG-P3 | P1 | Print assistance in the app: the agent explains the chosen orientation, supports and settings, fixes printability issues as patches, and reads a failed print's report back into suggestions | A printability issue is fixed by an agent patch and passes the fit and printability checks |

### 5.10 Refinement

| ID | Pri | Requirement | Accepted when |
|---|---|---|---|
| FR-RE-1 | P0 | **Critique loop**: run all checkers, have the model propose one patch per issue in priority order, preview each, accept or reject; bounded rounds | A golden task with seeded faults gets to zero blocking issues |
| FR-RE-2 | P0 | **Versions and compare**: any two versions side by side or overlaid, with a diff of params, parts, BOM cost and issues | |
| FR-RE-3 | P1 | **Goals**: "lighter", "cheaper", "fewer supports", "stronger at the hinge": code picks the metric, the model proposes changes, code measures before and after | Each accepted change shows its metric delta |
| FR-RE-4 | P1 | **Physical feedback**: after a print, record what went wrong (did not fit, broke, warped) on the part; it becomes an issue and feeds the next round and the examples store (FR-AI-10) | |
| FR-RE-5 | P2 | Param sweep: build N variants across a param range and chart the metric | Chart via the dataviz rules |

### 5.11 Many uses: process and domain packs

The Replicator is meant for many kinds of thing. A **pack** adds a process or a domain without touching the core:
knowledge cards, recipes, catalog entries, checkers, prompt snippets, export formats and golden tasks.

| Pack | Pri | Adds |
|---|---|---|
| FDM printing | P0 | Section 5.9 |
| Mechatronics | P0 | Motors, drivers, MCUs, sensors, the 5.6 and 5.7 checkers, robot and gadget recipes |
| Enclosures | P1 | Boards, ports, vents, standoffs, lids, gaskets |
| Props and cosplay | P1 | Wearable sizing, the split and fit rules for large prints, LED and sound kits, finishing steps |
| Laser and sheet | P2 | Flat parts from solids, finger joints, kerf, DXF or SVG export |
| Woodworking | P2 | Lumber sizes, cut list, joinery recipes |
| CNC | P2 | Tool access checks, stock, export for a CAM tool |
| Rooms (M2) | P2 | Already on the roadmap; fits as a pack |

**FR-PK-1** A pack is a folder with a manifest; enabling it adds its cards, recipes and checkers to retrieval.
**FR-PK-2** Each pack ships its golden tasks, and FR-AI-9 runs them.

## 6. Non-functional requirements

| ID | Requirement |
|---|---|
| NF-1 | **GPU rule.** The window stays on the iGPU. Slicers, solvers, CalculiX and Blender workers run with `CUDA_VISIBLE_DEVICES=` and are checked with `nvidia-smi --query-compute-apps` in tests. Only llama-swap or Strata (under Berth) touch the card. |
| NF-2 | **Network.** Off by default. With research on, only search words and part numbers leave. Printers are reached by tailnet address only. No telemetry. |
| NF-3 | **Speed.** Params slider rebuild under 100 ms for 200 ops; the full checker pass under 2 s; a slice under 60 s per plate on a desktop CPU; each model stage reports its time. |
| NF-4 | **Model budget.** A full concept-to-printable run on a golden task needs at most 25 model calls, and each call stays under the FR-AI-2 context budget. Logged per run. |
| NF-5 | **Determinism.** Every solver, checker and cost result is reproducible from the project folder alone. |
| NF-6 | **Testability.** `core/`, `knowledge/`, `catalog/` and the solvers import no Qt. Each card and recipe has tests. The golden suite runs headless with `--shot`. |
| NF-7 | **Safety.** FR-EL-9 flags, plus notices for load-bearing, food-contact, heat and child use. The tool never states a design is safe. |
| NF-8 | **Docs.** The README, the homelab guide (`guide/replicator.md`) and `state/changes.md` are updated with each phase. |

## 7. Phasing

Each phase ends with its golden tasks passing and shots in `out/`.

| Phase | Delivers | Why this order |
|---|---|---|
| W0 Foundation | Project layers (section 3), params and expressions, the claim kinds, the issues list, constrained decoding, the tool interface, the first knowledge cards and catalog (fasteners, bearings, FDM rules, PLA and PETG), the golden suite harness | Everything else stands on params, cards and checkers |
| W1 Printable | hole, fillet, split ops; printer profile; printability, orientation, split, slicing, 3MF, printed-part cost; Issues panel | First real output: a part on the bed |
| W2 Studio | Selection-scoped requests, ghost proposals with per-hunk accept, locks, params panel, stage mode, agent run view | Makes the rest usable live |
| W3 Breakdown and mechanics | Spec interview, scaffold, recipes (hinge, snap, boss, bearing seat, gears), joints, interference, fit classes, assembly steps, build sheet | Multi-part objects that fit together |
| W4 Wiring | Electrical catalog, netlist checks, power budget, wire sizing, harness routing, wiring diagram, enclosure pack | Mechatronic builds |
| W5 Sourcing and scaling | Full BOM, match to spec, live quotes (research lane), scaling with re-selection, make or buy | Costs to spec |
| W6 Refinement and packs | Critique loop, goals, physical feedback, version compare, props pack, then P2 packs | Improves everything before it |

## 8. Open questions for the operator

1. **Printer(s).** Answered 2026-11-14: a Bambu Lab printer first (model not chosen yet, arriving), Bambu LAN mode;
   other printers later. Still open: which model, and a row in `~/homelab/inventory/hosts.yaml` once it is on the
   network.
2. **Slicer.** PrusaSlicer or OrcaSlicer (neither is installed)? Both have a CLI.
3. **Currency and vendors.** USD? Which vendors for parts (Amazon, AliExpress, McMaster, Digi-Key, LCSC)? McMaster has
   no public price API; others need keys (FR-SO-8).
4. **Research lane for sourcing.** Is it acceptable for part numbers and search words to leave the machine when
   research is on (as Explain does today)?
5. **First golden tasks.** What are three things you actually want to build first? They become the W0 suite, and
   they decide which cards and recipes are written first.
6. **KiCad.** Is a custom PCB in scope (FR-EL-8), or are off-the-shelf boards and wiring enough?
