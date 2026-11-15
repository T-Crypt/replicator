# Session 5 (2026-11-14 evening): specify, STEP, MCP, endpoints, preview film

Read `AGENTS.md`, then `docs/COMPETITORS-2026-11-14.md` (the strategy; its top section is the current status).
Scope (operator): an engineering and research workshop for nearly anything, from houses and floor plans to boards,
household objects, machines and concepts. Never describe it as only a CAD tool.

- "Dream" is "specify" in every visible string; internal names (`studio.dream`, `client.dream`) are unchanged.
- STEP export (`core/step.py`): OCCT reads all 11 fixtures back as valid solids with the same volume. Sliver
  triangles join their neighbour (the rocket engine's actuators used to read back as open shells).
- MCP server (`replicator/mcp_server.py`, `.mcp.json`); an open window reloads agent edits as one undo step.
- `endpoints` in services.json add any OpenAI-compatible engine; keys stay in env vars.
- Preview film: `brag-output/brag.mp4` (56 s, scored, poster in frame 0), scripts in `tools/film/`, take via
  `tools/record.sh` (headless gamescope on the iGPU; `--shot` needs `WAYLAND_DISPLAY=wayland-1` from a plain shell).
- Checks: new `roof` (buildings) and tiered `size` (warn >15%, fix >40%) in `core/critique.py`, tests in
  `tests/test_roof_and_size.py`. They caught the README turbofan's fan, reverse vanes and turbine arrayed around
  the wrong axis; `fixtures/dirk_engine_v2.json` corrected and the README previews regenerated.
- More checks: `array_axis` (a full-circle radial array must spin about the round body holding its source),
  `alignment` (a part the plan says runs "along" another must point the same way) and `card_rules` (a knowledge
  card's `rise:` line bounds a part's elevation; `knowledge/desk_lamp.md` says a lamp arm rises 35 to 80 degrees).
  `array_copies` used to skip every program with named materials; fixed, and it found the turbofan's fan blades
  lying flat and fused (58%); blades now taper and pitch 60 degrees. Failing cases live in `tests/data/`.
- Open: `array_axis` misses a ring whose source sits in no visible round body (the broken turbofan's turbine
  vanes); `assets/range.jpg` and the film show the house before its ridge moved to the long side. STEP is faceted (planes
  only); analytic surfaces need the OCCT layer (P2). `cadquery-ocp` and `mcp` are now in the venv.

# Session 4 (2026-11-14): accuracy workshop, on branch `accuracy-workshop`

Read `AGENTS.md` first; it is the current map. Committed in small units (`git log main..accuracy-workshop`).
Verified with 60 pytest, `tools.check` on every fixture and headless shots (build, showcase, materials, context menu).

- New: `tube`, `nozzle` (Rao bell), `rotor` (NACA blades), `grille`; `core/critique.py` (floating, buried, clipping,
  off-axis, size, missing, tips); `core/physics.py` (mass, CG); knowledge cards; critique round in `client.dream`;
  scoped edits (`rework`, `fixIssues`); delete and duplicate components; aerospace materials and `swapMaterial`;
  `core/importers.py` (3MF, STEP/IGES, FBX/USD/ABC/.blend, gallery ZIPs); Blender collections per component;
  `fixtures/rocket_engine.json` from `tools/rocket_fixture.py`; `tools/check.py`.
- Fixed: Showcase vignette blacked out the stage; RMenu ignored live enabled/checked; unbounded params hung the kernel;
  stale job results could land on a newer build; numpy floats reached QML as garbage.
- Open: the STEP route is untested against a real CAD file; critique and mass run on the GUI thread (about 50 ms on
  fixtures, 0.5 s on a 400-op grid); right-click menus not yet tried with a real mouse.

# Handoff: workspace v2 + Explain (2026-11-13, end of session 3)

Read `docs/DESIGN.md` first (the review and the ten improvements), then this file. Nothing from session 3 is
committed yet: review `git status`, then commit in the three groups listed at the bottom.

Verify every step with a headless frame and the tests:

```sh
.venv/bin/python -m pytest -q                      # 36 pass
.venv/bin/python -m replicator.app fixtures/dirk_engine_v2.json --software --shot out/x.png \
    [--mode dissect|reverse|showcase] [--theme graphite] [--accent amber] [--ui commander|preferences|materials]
```

`--shot` never reads or writes the operator's preferences. In a hidden window the popup overlay has zero size, so
the dim behind Commander and Preferences does not show in shots; it does in the real window.

## Done in session 3 (working, shot-verified, not committed)

- **Structure.** `qml/Replicator/UI/` (design system module), `qml/panels/`, `qml/viewport/`. `Main.qml` holds one
  action registry that feeds the menus, the shortcuts and the Commander.
- **Design system.** `Theme.qml`: 4 themes, 6 accents, 3 densities, motion switch, persisted. Vector icon set
  (`Icon.qml`), `IconButton`, `Pill`, `Segmented`, `Chip`, `Kbd`, `RSlider`, `RCombo`, `RMenu`, `DockHeader`, `Swatch`.
- **New UI.** Start screen (examples, recents), Commander (`Ctrl+K`), Preferences (`Ctrl+,`), status bar with kernel
  read-outs, floating viewport bar, material shelf (27 presets), restyled managers, timeline and ledger, resizable
  dock, focus mode (`F11`).
- **Viewport.** Adaptive decimal grid (no horizon shimmer), reference planes for image-to-3D (old step 3: done),
  selection read-out.
- **Engine.** Edits validate on the shared cache, redo, bounded caches, cached row models, `studio.stats`.
- **Explain backend (no UI yet).** `research/lane.py` (bounded web lookup: Wikipedia API, optional SearXNG),
  `core/explain.py` (every sentence checked: cited / measured / concept), `llm/prompts/explain.md`,
  `research_queries.md`, grounded dreaming in `client.dream(sources=...)`, `config.py` (services file),
  `voice.py` (Kokoro/OpenAI-compatible TTS, espeak-ng, Whisper server or command), bridge slots `explain()`,
  `speak()`, `stopSpeaking()`, `toggleDictation()`, `setService()`, properties `explanation`, `restPose`,
  `services`, `speaking`, `listening`, mode `"present"`. Measured once: engine fixture, role `agent`, 50 s,
  4 cited / 10 measured / 11 concept sentences, 0 dropped (`out/explain_try.py` reruns it).

## Remaining work, in order

### 1. Present mode in the viewport (coder) - `qml/viewport/Viewport.qml`, `qml/Main.qml`
1. Add `property bool present: false` to `Viewport.qml`. In `Main.qml` add
   `readonly property bool present: studio.mode === "present"`, pass it down, and replace `chrome` with
   `!showcase && !present && !focusMode`.
2. Backdrop in `Main.qml` (the gradient `Rectangle`): when `present`, white to `#e6e9ee`; hide the vignette `Shape`.
3. In `Viewport.qml` when `present`: hide the grid; floor `PrincipledMaterial` white, `roughness 1`, opacity 1 (it
   only catches the shadow); `aoEnabled: true`, no fog, no vignette, no DOF; key light brightness about 2.0.
4. Levitate: `build.y: studio.ground + lift`, where `lift` is `studio.radius * 0.18` plus a slow sine bob
   (`FrameAnimation`, 4 s period, amplitude `radius * 0.012`) when `studio.restPose === "levitate"`, else 0.
5. Add `function frameComponent(cid)`: read `studio.components`, set `tPivot` to its `center` and `tDist` from its
   `size` (same formula as `frameSelected`). Empty id calls `frameAll(true)`.
6. Add the mode to the header `Segmented` (`{ key: "present", label: "Present", icon: "present", hint: "5" }`) and
   an action `mode.present` with key `5`. Also add an action `explain` ("Explain how it works", icon `book`,
   `studio.explain()`), and a Pill for it in `LedgerPanel.qml` next to "Name parts".
7. Check: `--mode present` shot of the engine (floats) and of `out/image3d/orc-mv/program.json` (stands).

### 2. Presenter overlay (coder) - new `qml/panels/Presenter.qml`
**Done 2026-11-13** (shot-verified with `out/present-test` and the empty state). The window Shortcuts own Esc, Space,
Left and Right, so Main.qml routes those actions to the presenter while presenting; `speaking` notifies via `voiceChanged`.

Shown over the viewport when `present`. Fixed light palette (ink `#14181f`, dim `#5b6472`), not theme tokens.
- State: `property int chapter: 0`, `property bool playing: true`. `readonly property var doc: studio.explanation`.
- On chapter change: `window.isolate = doc.chapters[chapter].component`, `viewport.frameComponent(...)`, and
  `if (studio.services.speak) studio.speak(doc.chapters[chapter].text)`.
- Advance: a `Timer` with `interval: chapters[chapter].seconds * 1000` when not speaking; when speaking, advance on
  `studio.speakingChanged` going false. Keys: Left, Right, Space, Esc (leave to Reverse).
- Layout: title and, if `doc.concept`, an amber "CONCEPT" badge with `doc.notice` (icon `alert`) top left; a caption
  card bottom centre with the chapter title and its sentences; after each sentence a chip: `[n]` in the accent for
  cited, a ruler icon for measured, "concept" in amber. Progress dots, previous / play / next, a speaker toggle.
- Sources list on the right: number, title, domain; click runs `Qt.openUrlExternally(url)`.
- Empty state (no `doc.chapters`): one card with an "Explain how it works" Pill, and a line saying web research is
  off when `!studio.services.research`.
- Do not show anything the document does not contain. No decorative HUD rings or fake telemetry.

### 3. Services in Preferences (coder) - `qml/panels/Preferences.qml`
A "RESEARCH AND VOICE" section: toggles `research` and `speak` (`studio.setService(key, JSON.stringify(v))`), text
fields `search_url`, `tts_url`, `tts_voice`, `stt_url`, `stt_cmd`, and the status lines from
`studio.services.status`. State plainly: research sends only search words; voice never uses the RTX card.

### 4. Dictation button (coder) - `qml/Main.qml`, the dream capsule
An `IconButton` (icon `mic`, `on: studio.listening`) visible only when `studio.services.status.stt !== ""`, calling
`studio.toggleDictation()`. `Connections { target: studio; function onDictated(t) { prompt.text = t } }`.
The operator then presses Enter; do not auto-submit.

### 5. Voice setup (operator decision, then agent)
Nothing was installed. Kokoro on galaxy did not answer on 2026-11-13. Ask the operator which they want:
Kokoro-FastAPI on the CPU (`CUDA_VISIBLE_DEVICES=`), a second machine, or espeak-ng only; and whisper.cpp
(`whisper-cli`, CPU) or a faster-whisper server for dictation. Per the GPU rule neither may touch the 4090.

### 6. Wider web search (operator decision)
Public search sites answer scripts with a bot check and the lane does not work around it, so today the lane reads
Wikipedia only. A SearXNG guest (community script, tailnet only, inventory row) would open the wider web: ask first.

### 7. Showcase lighting (coder, small)
Showcase still reads flat and grey on dark materials (`out/review/a-show.png`). Try: lower the floor
`specularAmount`, `glowBloom` 0.15, and check whether the haze is the SSAO pass by toggling `aoEnabled`.

### 8. README and docs (writer) - required before this counts as done
- README: new previews from the commands above (build, dissect, reverse with reference planes, start screen,
  Commander, material shelf in Daylight, Present once step 2 lands) into `assets/`; sections for the workspace,
  themes, Commander, materials, Image to 3D (real flow, 34 s on the card), Explain and Present (the three sentence
  kinds, the concept notice, what is and is not guaranteed), voice (optional), updated project layout and roadmap.
  "What Replicator never does" must change: it now reads the web when research is on (search words only); it still
  never calls a cloud model.
- `~/homelab/guide/replicator.md`, `~/homelab/state/changes.md` (the old step 6 items still stand), STATUS.md.

### 9. Later (roadmap, not started)
- **3D printers** (operator note, 2026-11-13): after Explain, send a build to a printer. Printability check
  (overhangs, wall thickness, bed fit), orient and split by component, slice through a CLI slicer, send to
  OctoPrint / Moonraker on the tailnet, show progress in the status bar.
- Split `qt/bridge.py` (now about 1,000 lines) into document, jobs, voice and explain services behind `Studio`.
- Node editor over the op DAG, four-up viewport, Holodeck "Replicate" action (old step 4), texturing lane.

## Commit groups (no AI attribution)
1. `qml/`, `shaders/`, `replicator/app.py`: workspace v2 (design system, action registry, panels, viewport).
2. `replicator/core/materials.py`, `qt/library.py`, `qt/bridge.py`, `core/evaluate.py`, `qt/mesh_geometry.py`:
   engine and bridge features.
3. `replicator/research/`, `core/explain.py`, `config.py`, `voice.py`, `llm/`, `tests/test_explain.py`, docs.

## Rules for whoever picks this up
- The GPU is reached only through `comfy.acquire()` (Berth) and llama-swap. Never load models in-process.
- One GPU job at a time. Local agent output is a draft: run the shot and `pytest -q` before committing.
- Qt APIs: check `~/docs-local` first. A `Behavior on y` whose target moves every frame stalled here; animate a
  0..1 factor and compute the position from it (see the dream capsule in `Main.qml`).
- `out/` is gitignored; `out/shot.sh <name> [args]` writes `out/review/<name>.png`.
