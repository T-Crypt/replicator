# Replicator status (2026-11-13, end of session 1)

**Session 2 (2026-11-13 late): README, Blender MCP and the image-to-3D backend are done. Next steps for agents: HANDOFF.md.**

"You dream it, you build it." Private repo T-Crypt/replicator, checkout ~/projects/replicator. Plan of record:
~/.claude/plans/i-want-some-kind-ancient-honey.md (decisions, milestones, operator leads). Operator guide:
~/homelab/guide/replicator.md. Open it with SUPER+SHIFT+H or ./launch.sh [program.json | model.glb].

## Working (verified with headless shots, live Blender/Cycles runs, 26 pytest)
- Text -> blueprint -> BuildProgram on Dirk-27B (llama-swap `dirk`, xhigh), repair rounds, JSON-Patch edits.
- Kernel: manifold3d, ~10-60 ms per build; ops box/cylinder/sphere/torus/capsule/extrude/revolve/loft/pipe/helix/gear/
  mesh + transform/array/smooth/round/shell/deform + boolean/hull/group; each op has a `component`.
- C4D-style QML workspace (PySide6 + Qt Quick 3D 6.12, Intel iGPU only, self-check quits if on the 4090): custom
  damped camera, F1-F4 views, axis triad, move gizmo, Object/Attribute managers, timeline (build + reverse).
- Modes: Build, Dissect (exploded views + callouts), Reverse (mesh import -> pieces, patterns, contacts, assembly
  order, observed/inferred/unknown ledger, Name parts), Showcase (stage, SSAO/DOF/fog, turntable, Cycles CPU still ~7 s).
- Blender 5.2.3 + vendored mcp-for-blender (pinned 8f40787, update check off, telemetry off, localhost:9876):
  Render > Open in Blender / Pull back from Blender (round trip into Reverse) verified.
- Headless check: `.venv/bin/python -m replicator.app <file> --software --shot out/x.png [--mode dissect|reverse|showcase] [--explode 0.9]`
  (the Qt `offscreen` platform cannot run Quick3D; --shot loads the window hidden instead).

## Not verified yet
- Camera/gizmo feel with a real mouse (operator to test). Dirk's dream since the "radial rings follow the body
  axis" prompt rule (no new dream run since). Name parts against a live model.

## Next (pick from these)
1. Operator answer pending: register the mcp-for-blender MCP server in omp/opencode (harness configs are generated
   from homelab; ask before changing).
2. Holodeck character sheet -> Replicator live import (queued by the operator; reference planes + image-to-3D).
3. M3 image-to-3D lane (Meshy-like, local): TRELLIS.2 or Hunyuan3D 2.x under Berth; IDOL as the fast splat preview.
4. Blueprint-maker sheet (shrugg0/blueprint-maker) from the Blueprint slider; GPU Cycles under a Berth lease.
5. M2 floor plan -> rooms (Sims build mode); M4 sculpt and node editor.
Known rough edges: tool-palette glyphs are font symbols; loft shading shows facet ribs; Showcase lighting is moody
on dark materials.
