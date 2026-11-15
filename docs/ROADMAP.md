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
| Installable by anyone: `pip install -e ".[all]"`, generic engines, GPU policy | A clean venv passes the suite; the core-only install passes with Qt, MCP and OCCT tests skipped |

## Next

| Work | Why | Check |
|---|---|---|
| Measure tool in the viewport (distance, angle, radius) | The most asked-for missing tool in browser CAD (Chili3D issue tracker) | Two picked points report the distance the kernel measures |
| Navigation without a middle mouse button | Laptop and trackpad users (Chili3D issue tracker) | Orbit, pan and zoom work with one button plus a modifier |
| URDF and MJCF out, inertias from the exact solid | The longest thread on text-to-cad's tracker; robotics users | A MuJoCo scene of a Replicator arm loads and reports the same mass |
| DXF out from the drawing sheet | Asked for on CADAM; laser cutting and CAD hand-off | The sheet opens in LibreCAD with its views and dimensions |
| Scale-aware printability (FR-PR-15) | Most prints are replicas, and thin parts vanish at 1:50 | A 1:50 house lists the mullions that drop under 0.4 mm and the thicken edit makes them printable |
| Slicing and send to printer, print queue (FR-PR-16 to 18) | Closes the print loop for those who print | A print starts after one confirm; the queue survives a restart |
| Joints and mates as program data, with a mate check | Assemblies; feeds URDF | A drone fixture with named joints; a rotor through an arm fails the check |
| Reverse to program | The unique lane: an unknown mesh becomes an editable program | An imported model rebuilds within tolerance, unknowns listed |
| Packaged app and first-run endpoint picker | People who do not use pip | A clean machine runs a build in under 10 minutes |

## Declined

- **No feature-tree CAD.** A procedural op history with a timeline is a different, simpler thing.
- **No OCCT kernel swap.** manifold3d is why a model can iterate in milliseconds; an OCCT layer may
  come later for fillets and native STEP, beside it, not instead of it.
- **No benchmark that cannot be scored twice to the same digit.**
