# Roadmap

Each line names the check that proves it. Done items stay listed with their proof, so the record
shows what was verified, not only what was planned.

## Done

| Work | Check |
|---|---|
| MCP server: read, patch, build, check, export, sheet, specify, reverse, print fit | Driven end to end over stdio by the SDK client; a rejected patch leaves the file byte-identical |
| Model endpoints: any OpenAI-compatible URL, key from the environment | The same fixture specified through two different endpoints passes `tools.check` |
| STEP export | Every fixture reads back in OpenCASCADE as valid solids, volume within 4e-7 |
| Corpus export | Two exports are byte-identical; every row re-verifies; a tampered row is caught |
| Benchmark v0: four seeded tasks, deterministic scorer | The same program and seed re-score to the same digit |
| Printer profiles, never-exceed gating, fit, orient and scale to the bed | A part 1 mm too tall is refused naming the axis; scale to fit gives the exact factor and the scaled build passes |
| Installable by anyone: `pip install -e ".[all]"`, generic engines, GPU policy | A clean venv passes the suite; CI runs Python 3.11 and 3.13, full and core-only installs, and checks every fixture |
| Measure tool (distance with X, Y, Z parts) | Two points across the house slab read 14160.5 mm, the computed diagonal |
| Navigation with any mouse: Shift+drag pans, Ctrl+drag zooms | Orbit, pan and zoom with one button |
| Installable from PyPI as `replicator-workshop` (pip or pipx), with the window, shaders and examples inside the package | CI installs the built wheel into a fresh venv and builds an example from outside the checkout; the installed app opens its start screen with all nine examples |
| DXF out: the drawing's views at 1:1 in model units, on OUTLINE, EDGES, SECTION, DIMS and TEXT layers | ezdxf reads every fixture with no audit errors; the plate's section shows its 20 mm hole as a gap at 50 to 70 mm (`tests/test_dxf.py`) |
| URDF and MJCF out, inertias from the exact solid (links fixed to a base until joints exist) | MuJoCo loads the MJCF with the mass Replicator reports and the model comes to rest upright (`tests/test_robot.py`, run in CI with the `sim` extra) |

## Next

| Work | Why | Check |
|---|---|---|
| Scale-aware printability (FR-PR-15) | Most prints are replicas, and thin parts vanish at 1:50 | A 1:50 house lists the mullions that drop under 0.4 mm and the thicken edit makes them printable |
| Slicing and send to printer, print queue (FR-PR-16 to 18) | Closes the print loop for those who print | A print starts after one confirm; the queue survives a restart |
| Joints and mates as program data, with a mate check | Assemblies; feeds URDF | A drone fixture with named joints; a rotor through an arm fails the check |
| Reverse to program | The unique lane: an unknown mesh becomes an editable program | An imported model rebuilds within tolerance, unknowns listed |
| One-click app (AppImage or Flatpak) and first-run endpoint picker | People who do not use pip | A clean machine runs a build in under 10 minutes |

## Declined

- **No feature-tree CAD.** A procedural op history with a timeline is a different, simpler thing.
- **No OCCT kernel swap.** manifold3d is why a model can iterate in milliseconds; an OCCT layer may
  come later for fillets and native STEP, beside it, not instead of it.
- **No benchmark that cannot be scored twice to the same digit.**
