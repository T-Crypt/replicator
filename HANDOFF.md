# Handoff: M3 image to 3D (2026-11-13, end of session 2)

Read STATUS.md first, then this file. Plan of record: `~/.claude/plans/i-want-some-kind-ancient-honey.md`.

## Done this session (committed and verified)

1. **README**: banner and how-it-works SVGs drawn by `tools/readme_art.py` (rerun it after editing), four mode
   previews in `assets/`, full README. The README's example program builds (checked with `Evaluator().run`).
2. **Blender MCP** registered in OMP, OpenCode, Pi and Empryo (homelab `harnesses/agents/mcp-servers.json`, entry
   `blender`). Wrapper `tools/blender-mcp`, server `uv tool` `mcp-for-blender` pinned at 8f40787. Handshake lists 10 tools.
3. **Image to 3D backend, headless, works end to end:**
   - Weights on `/data/models/hunyuan3d/`: Hunyuan3D 2.1 (single image), Hunyuan3D-2mv (multi-view), BiRefNet.
     Registered in `~/comfy/extra_model_paths.yaml` (backup `.bak-20261113-hunyuan3d`) and its homelab mirror
     `reference/comfyui-extra_model_paths.yaml`.
   - `replicator/image3d/sheet.py`: splits a Holodeck sheet into views (labels come from the prompt sidecar), drops
     watermarks and specks, centres every view on white at one shared scale.
   - `replicator/image3d/comfy.py`: gets the card through homelab `bridge.ensure_up()` (Berth), uploads views, runs the
     BiRefNet mask workflow and the Hunyuan workflow, then releases the batch.
   - `replicator/image3d/pipeline.py`: CLI `python -m replicator.image3d.pipeline <png> [--single] [--side-as right]
     [--height MM]`. It writes `out/image3d/<name>/{views/, raw.glb, model.glb, program.json, reverse_report.json,
     image3d.json}`.
   - Measured on the orc sheet (`/mnt/models/comfy/output/characters/sheet-fantasy_00001_.png`): **34 s on the card**.
     The raw surface had 303k triangles in 24k pieces. The pipeline kept 4 parts, 150k triangles, at 1800 mm tall.
     The result opens cleanly: `./launch.sh out/image3d/orc-mv/program.json` shows one component plus the evidence ledger.
4. `app.py --shot` now waits for a running job before it grabs the frame. `bridge.py` loads the report for image-to-3D
   programs (any program that has a `reference` key).

## Remaining work, in order

Each step is small enough for a local agent (`coder` for code, `agent` for docs). Verify each one with the headless shot:
`.venv/bin/python -m replicator.app <program.json> --software --shot out/x.png --mode reverse`

### 1. Bridge slots (coder) - `replicator/qt/bridge.py`
- Add a `@Slot(str, bool) imageTo3D(path, single)`. Run it through `self._run_job("Image to 3D", job, mode_after="reverse")`.
  The job calls `pipeline.image_to_mesh(Path(path), single=single, log=log)` and returns
  `{"program": json.loads(Path(info["program"]).read_text()), "project": str(Path(info["program"]).parent)}`.
  Copy the pattern of `importModel` exactly.
- Add a `holodeckSheets` Property (list of dicts: `path`, `name`, `subject`, `mtime`), newest first, built from
  `sheet.CHARACTERS` `*.png` (skip `*.png.json`). Use `sheet.subject(sheet.sidecar(p))` for the subject.
  Add a `QFileSystemWatcher` on that directory that emits `holodeckChanged`.
- Test: call `studio.imageTo3D(...)` from a tiny script, or temporarily from `app.py`, and check that the shot shows the orc.

### 2. Holodeck deck panel (coder) - new `qml/HolodeckPanel.qml`
- Show it in Reverse mode above `LedgerPanel`, or as a third tab in `Main.qml`'s right dock: thumbnails
  (`Image { source: "file://" + path }`), the subject text, and two Pills: **"Make 3D (sheet)"** calls
  `studio.imageTo3D(path, false)`, **"Front only"** calls `imageTo3D(path, true)`. Disable both while `studio.busy !== ""`.
- Add `File > Image to 3D…` (a FileDialog for any png/jpg, which calls `imageTo3D(path, false)`) next to the Import item.
- Match the style in `Theme.qml` and `Pill.qml`. Verify Qt APIs in `~/docs-local` before using them.

### 3. Reference planes (coder) - `qml/Viewport.qml`
- When `studio.reference` (a new Property: the program's `reference.views` as absolute paths) is not empty, draw one
  `Model { source: "#Rectangle" }` per view with a `DefaultMaterial` (`lightingMode: DefaultMaterial.NoLighting`,
  `diffuseMap: Texture { source }`, `opacity: 0.55`). Place them C4D-style: front on -Z facing +Z, left on -X, back
  on +Z, right on +X. Size them to the model height, standing on the floor.
- Add a View menu toggle "Reference images". The `views/<key>.png` images are already 512 px squares on white.

### 4. Holodeck "Replicate" action (agent, in homelab; ask the operator first, since it touches Holodeck)
- In `~/homelab/scripts/comfy/holodeck/studios.json` / the Characters UI: a button that runs
  `~/projects/replicator/launch.sh <sheet.png>`. Then make `app.py` treat a `.png`/`.jpg` argument as `imageTo3D`.
  `launch.sh` single-instance focus needs a way to pass the file to the running app (simplest: a small socket or
  a `--send` flag; or start a second instance only when given a file).

### 5. Quality passes (coder, optional)
- `--side-as`: the orc ran with side as `left`. Run once with `right` and compare (look at the arm and cloak). Keep the better one as the default.
- Surface pits: try `octree=384` in `mesh_workflow` (slower, finer), or the `basic` algorithm with threshold 0.5.
- Texturing (Meshy-style): Hunyuan3D 2.1 paint is not native in ComfyUI. Evaluate TRELLIS.2 (MIT, PBR) as the textured lane.

### 6. Docs (agent) - required before the feature counts as done
- `~/homelab/guide/replicator.md`: an "Image to 3D" section (CLI, timings, where weights live, licence: Tencent Hunyuan
  community licence, not for EU/UK/KR).
- `~/homelab/state/changes.md`: a dated entry for the weights and the extra_model_paths change. The undo: delete the
  `hunyuan3d:` block, `rm -r /data/models/hunyuan3d`, `uv tool uninstall mcp-for-blender`.
- README "Image to 3D" section: replace "being built" with the real flow. Tick the M3 roadmap box once steps 1 to 3 land.
- STATUS.md: move items to Working.

## Rules for whoever picks this up
- The GPU is reached only through `comfy.acquire()` (Berth). Never load models in-process; the app stays on the iGPU.
- One GPU job at a time. Check `berth status` first; Dirk-27B is usually resident and gets parked automatically.
- Local agent output is a draft: run the headless shot and `pytest -q` before committing. No AI attribution in commits.
- `out/` is gitignored; test artefacts stay there.
