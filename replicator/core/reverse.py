"""Reverse engineering: take a finished model apart and explain how it is made.

Method (adapted from the REA skill's investigation discipline):
  1. Route the input: a BuildProgram already knows its own history; an imported mesh (GLB/glTF/OBJ/STL/PLY) has to
     be decomposed from geometry alone.
  2. Summary first: an inventory of pieces and components before any detail.
  3. Evidence ledger: every claim is `observed` (measured from the geometry, with the measurement as evidence),
     `inferred` (a reading of observations, with the rule or the model that made it and a confidence), or `unknown`.
     The UI shows the tag; a guess never passes as a measurement.
  4. Trace: each component links to the pieces and (for programs) the build steps that produce it.
  5. Close with a checklist of the questions asked and whether each is answered, partly answered or unresolved.

Nothing here touches a GPU. The optional naming pass (llm.client.name_components) only labels; it is tagged
`inferred` with the model's name as its source.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import trimesh

MAX_TRIANGLES = 3_000_000  # a bigger scene takes minutes to split and bloats the project; decimate it first
MAX_PIECES = 400          # beyond this, tiny pieces are merged into their nearest large neighbour
SIG_TOL = 0.03            # 3 % tolerance when grouping identical pieces


def ledger_entry(claim: str, kind: str, evidence: str, subject: str = "", confidence: float | None = None) -> dict:
    assert kind in ("observed", "inferred", "unknown")
    e = {"claim": claim, "kind": kind, "evidence": evidence, "subject": subject}
    if confidence is not None:
        e["confidence"] = round(float(confidence), 2)
    return e


# ---------------------------------------------------------------- import
def load_pieces(path: Path) -> tuple[list[trimesh.Trimesh], dict]:
    """Every connected piece of the model in world space, Y-up, plus facts about the file."""
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"{path.name} is empty or missing")
    try:
        loaded = trimesh.load(str(path), force="scene")
    except Exception as e:  # noqa: BLE001 - trimesh raises a dozen types for a broken file
        raise ValueError(f"{path.name} could not be read as a 3D model ({e})") from None
    tris = sum(len(g.faces) for n in loaded.graph.nodes_geometry
               if isinstance(g := loaded.geometry.get(loaded.graph[n][1]), trimesh.Trimesh))   # instances count
    if tris > MAX_TRIANGLES:
        raise ValueError(f"{path.name} has {tris:,} triangles; the limit is {MAX_TRIANGLES:,}. Decimate it "
                         "(Blender's Decimate modifier) and import again")
    meshes = []
    dumped = loaded.dump(concatenate=False)    # bakes every node transform into world space
    nodes = len(dumped)
    for g in dumped:
        if isinstance(g, trimesh.Trimesh) and len(g.faces):
            for piece in g.split(only_watertight=False):
                if len(piece.faces) >= 4:
                    meshes.append(piece)
    facts = {"file": path.name, "format": path.suffix.lower().lstrip("."), "nodes": nodes,
             "pieces_raw": len(meshes), "triangles": int(sum(len(m.faces) for m in meshes))}
    return meshes, facts


def unit_hint(fmt: str, longest: float) -> dict:
    """Mesh files carry no reliable units. Say what the size suggests; the model is never rescaled silently."""
    if longest < 2:
        return ledger_entry(f"longest side is {longest:.3g}: probably metres (or inches), not millimetres; "
                            "Replicator reads file units as mm and did not rescale", "inferred",
                            "a real part under 2 mm is rare; glTF is metres by specification, OBJ and PLY unspecified",
                            confidence=0.6)
    if fmt in ("stl", "3mf"):
        return ledger_entry("units are millimetres", "inferred", f"{fmt.upper()} from printers is mm by convention",
                            confidence=0.7)
    return ledger_entry("units assumed millimetres", "inferred", f"{fmt.upper()} has no unit field", confidence=0.4)


def _merge_small(meshes: list[trimesh.Trimesh]) -> tuple[list[trimesh.Trimesh], int]:
    if len(meshes) <= MAX_PIECES:
        return meshes, 0
    meshes = sorted(meshes, key=lambda m: -float(np.prod(np.ptp(m.bounds, axis=0))))
    keep, small = meshes[:MAX_PIECES], meshes[MAX_PIECES:]
    centers = np.array([k.bounds.mean(0) for k in keep])
    groups = defaultdict(list)
    for s in small:
        groups[int(np.argmin(np.linalg.norm(centers - s.bounds.mean(0), axis=1)))].append(s)
    for i, extra in groups.items():
        keep[i] = trimesh.util.concatenate([keep[i], *extra])
    return keep, len(small)


# ---------------------------------------------------------------- per-piece observations
def piece_facts(m: trimesh.Trimesh) -> dict:
    lo, hi = m.bounds
    ext = hi - lo
    wt = bool(m.is_watertight)
    vol = float(abs(m.volume)) if wt else None
    bbox_vol = float(np.prod(np.maximum(ext, 1e-9)))
    fill = vol / bbox_vol if vol else None
    try:   # principal moments: rotation-invariant, so rotated copies in an array still match
        inertia = sorted(float(x) for x in m.principal_inertia_components)
    except Exception:  # noqa: BLE001
        inertia = [0.0, 0.0, 0.0]
    return {"lo": lo.tolist(), "hi": hi.tolist(), "extent": ext.tolist(), "center": ((lo + hi) / 2).tolist(),
            "watertight": wt, "volume": vol, "area": float(m.area), "faces": int(len(m.faces)), "fill": fill,
            "inertia": inertia}


def primitive_guess(f: dict) -> tuple[str, float, str]:
    """(shape, confidence, rule) from the fill ratio and extents. A reading of observations, so `inferred`."""
    e = np.array(sorted(f["extent"]))
    fill = f["fill"]
    if fill is None:
        return "open surface", 0.5, "not watertight, so no volume; likely a shell or a decal surface"
    near = lambda a, b, t=0.08: abs(a - b) <= t * max(a, b)  # noqa: E731
    if fill > 0.93:
        return ("plate" if e[0] < 0.12 * e[2] else "block"), 0.8, f"fills {fill:.0%} of its bounding box"
    if near(fill, math.pi / 4, 0.1) and near(e[1], e[2]) or near(fill, math.pi / 4, 0.1) and near(e[0], e[1]):
        return ("disc" if e[0] < 0.3 * e[2] else "cylinder"), 0.7, f"fill {fill:.0%} ~ pi/4 with two equal extents"
    if near(fill, math.pi / 6, 0.12) and near(e[0], e[2], 0.1):
        return "sphere", 0.7, f"fill {fill:.0%} ~ pi/6 and all extents equal"
    if near(fill, math.pi / 12, 0.15) and near(e[1], e[2]):
        return "cone", 0.5, f"fill {fill:.0%} ~ pi/12"
    if fill < 0.25:
        return "frame or shell", 0.5, f"fill only {fill:.0%}: hollow, thin-walled or branching"
    return "freeform", 0.4, f"fill {fill:.0%} matches no simple primitive"


def signature(f: dict) -> tuple:
    """Rotation-invariant: volume (or area for open pieces), area, and the cube roots of the principal moments."""
    mom = tuple(abs(x) ** (1 / 3) for x in f.get("inertia", [0, 0, 0]))
    return ((f["volume"] or f["area"]), f["area"]) + mom


def same_sig(a: tuple, b: tuple) -> bool:
    return all(abs(x - y) <= SIG_TOL * max(abs(x), abs(y), 1e-6) for x, y in zip(a, b))


# ---------------------------------------------------------------- patterns
def find_patterns(facts: list[dict]) -> list[dict]:
    """Groups of identical pieces, and whether each group is a radial or linear array (observed geometry)."""
    groups: list[list[int]] = []
    sigs = [signature(f) for f in facts]
    for i, sig in enumerate(sigs):
        for g in groups:
            if same_sig(sigs[g[0]], sig):
                g.append(i)
                break
        else:
            groups.append([i])
    out = []
    for g in groups:
        if len(g) < 2:
            continue
        P = np.array([facts[i]["center"] for i in g])
        entry = {"pieces": g, "count": len(g), "kind": "repeated"}
        c = P.mean(0)
        for ax in range(3):                         # radial: equal distance from an axis through the centroid
            r = np.linalg.norm(np.delete(P - c, ax, axis=1), axis=1)
            if len(g) >= 3 and r.mean() > 1e-6 and r.std() / r.mean() < 0.04:
                ang = np.sort(np.arctan2(*np.delete(P - c, ax, axis=1).T[::-1]))
                steps = np.diff(np.r_[ang, ang[0] + 2 * np.pi])
                if steps.std() / (steps.mean() or 1) < 0.08:
                    entry.update(kind="radial", axis="xyz"[ax], radius=float(r.mean()), center=c.tolist())
                    break
        if entry["kind"] == "repeated" and len(g) >= 3:   # linear: collinear and evenly spaced
            d = P - P[0]
            u = d[np.argmax(np.linalg.norm(d, axis=1))]
            u = u / (np.linalg.norm(u) or 1)
            t = d @ u
            perp = np.linalg.norm(d - np.outer(t, u), axis=1)
            ts = np.sort(t)
            if perp.max() < 0.02 * (ts[-1] - ts[0] + 1e-9) and np.diff(ts).std() < 0.05 * np.diff(ts).mean():
                entry.update(kind="linear", spacing=float(np.diff(ts).mean()), direction=u.tolist())
        out.append(entry)
    return out


# ---------------------------------------------------------------- contacts and order
def contacts(facts: list[dict], tol_frac: float = 0.01) -> list[tuple[int, int]]:
    lo = np.array([f["lo"] for f in facts])
    hi = np.array([f["hi"] for f in facts])
    tol = tol_frac * float((hi.max(0) - lo.min(0)).max())
    pairs = []
    for i in range(len(facts)):
        ov = np.all((lo[i] - tol <= hi) & (lo <= hi[i] + tol), axis=1)
        for j in np.nonzero(ov)[0]:
            if j > i:
                pairs.append((i, int(j)))
    return pairs


def disassembly_order(facts: list[dict], pairs: list[tuple[int, int]]) -> list[int]:
    """Peel the outermost, least-connected pieces first; assembly order is the reverse (inferred)."""
    deg = defaultdict(int)
    for i, j in pairs:
        deg[i] += 1
        deg[j] += 1
    C = np.mean([f["center"] for f in facts], axis=0)
    span = max(float(np.ptp(np.array([f["center"] for f in facts]), axis=0).max()), 1e-9)
    score = {i: np.linalg.norm(np.array(f["center"]) - C) / span - 0.15 * deg[i]
             - 0.5 * (f["volume"] or 0) ** (1 / 3) / span for i, f in enumerate(facts)}
    return sorted(score, key=lambda i: -score[i])


# ---------------------------------------------------------------- the whole analysis
def analyze_mesh(path: Path, project: Path) -> tuple[dict, dict]:
    """(program, report). Writes one .npz per piece into project/assets/ and returns a BuildProgram whose ops are
    those pieces in assembly order, grouped into components; the report holds the ledger and the checklist."""
    meshes, facts_file = load_pieces(path)
    if not meshes:
        raise ValueError("no triangle geometry in that file")
    meshes, merged = _merge_small(meshes)
    facts = [piece_facts(m) for m in meshes]
    ledger = [ledger_entry(f"{facts_file['pieces_raw']} connected pieces, {facts_file['triangles']:,} triangles",
                           "observed", f"trimesh split of {facts_file['file']} ({facts_file['nodes']} mesh nodes)")]
    if merged:
        ledger.append(ledger_entry(f"{merged} tiny pieces folded into their nearest large piece", "observed",
                                   f"cap of {MAX_PIECES} pieces for interactivity"))
    lo = np.min([f["lo"] for f in facts], axis=0)
    hi = np.max([f["hi"] for f in facts], axis=0)
    ext = hi - lo
    ledger.append(ledger_entry(f"overall size {ext[0]:.1f} x {ext[1]:.1f} x {ext[2]:.1f} (file units)", "observed",
                               "union of piece bounding boxes"))
    ledger.append(unit_hint(facts_file["format"], float(ext.max())))
    if float(ext.max()) < 2:
        facts_file["suggested_scale"] = 1000
    wt = sum(f["watertight"] for f in facts)
    ledger.append(ledger_entry(f"{wt} of {len(facts)} pieces are closed solids", "observed",
                               "trimesh is_watertight; open pieces can be shown and exploded but not used in CSG"))

    patterns = find_patterns(facts)
    in_pattern = {}
    for k, p in enumerate(patterns):
        for i in p["pieces"]:
            in_pattern[i] = k
        if p["kind"] == "radial":
            ledger.append(ledger_entry(f"radial array of {p['count']} identical pieces around {p['axis'].upper()}",
                                       "observed", f"equal radius {p['radius']:.2f} and equal angular steps",
                                       subject=f"pattern {k}"))
        elif p["kind"] == "linear":
            ledger.append(ledger_entry(f"linear array of {p['count']} pieces, spacing {p['spacing']:.2f}", "observed",
                                       "collinear centres, even spacing", subject=f"pattern {k}"))
        else:
            ledger.append(ledger_entry(f"{p['count']} identical pieces (no regular layout)", "observed",
                                       "matching extents and volume within 3 %", subject=f"pattern {k}"))

    pairs = contacts(facts)
    ledger.append(ledger_entry(f"{len(pairs)} touching or overlapping piece pairs", "observed",
                               "bounding-box contact within 1 % of the model size"))
    order = disassembly_order(facts, pairs)
    assembly = order[::-1]
    ledger.append(ledger_entry("assembly order: inner, large, well-connected pieces first", "inferred",
                               "peel order by distance from centre, contact count and size", confidence=0.6))

    # components: each pattern is one component; other pieces are grouped with what they touch, largest first
    comp_of: dict[int, str] = {}
    comps: list[dict] = []
    for k, p in enumerate(patterns):
        cid = f"c{len(comps) + 1}"
        shape, conf, rule = primitive_guess(facts[p["pieces"][0]])
        label = f"{p['kind'].title()} set x{p['count']} ({shape})" if p["kind"] != "repeated" else \
            f"Repeated {shape} x{p['count']}"
        comps.append({"id": cid, "label": label, "role": "", "evidence": "observed pattern"})
        for i in p["pieces"]:
            comp_of[i] = cid
    adj = defaultdict(set)
    for i, j in pairs:
        adj[i].add(j)
        adj[j].add(i)
    rest = sorted((i for i in range(len(facts)) if i not in comp_of), key=lambda i: -(facts[i]["volume"] or 0)
                  - facts[i]["area"] * 1e-3)
    target = max(4, min(16, int(len(rest) ** 0.5) + 2))
    seeds = rest[:target]
    for s in seeds:
        cid = f"c{len(comps) + 1}"
        shape, conf, rule = primitive_guess(facts[s])
        comps.append({"id": cid, "label": f"{shape.title()} group", "role": "", "evidence": "largest piece seed"})
        comp_of[s] = cid
    for i in rest:
        if i in comp_of:
            continue
        touching = [comp_of[j] for j in adj[i] if j in comp_of]
        if touching:
            comp_of[i] = max(set(touching), key=touching.count)
        else:
            C = np.array(facts[i]["center"])
            comp_of[i] = comp_of[min(seeds, key=lambda s: np.linalg.norm(np.array(facts[s]["center"]) - C))]

    # assets + ops in assembly order
    assets = project / "assets"
    assets.mkdir(parents=True, exist_ok=True)
    mats = {"observed": {"base_color": [0.72, 0.74, 0.78], "metalness": 0.6, "roughness": 0.4}}
    ops = []
    for n, i in enumerate(assembly, 1):
        m = meshes[i]
        rel = f"assets/piece_{i:04d}.npz"
        np.savez_compressed(project / rel, V=np.asarray(m.vertices, np.float32), F=np.asarray(m.faces, np.uint32))
        shape, conf, rule = primitive_guess(facts[i])
        ops.append({"id": f"p{i:04d}", "op": "mesh", "label": f"{shape.title()} {n}", "part": shape,
                    "component": comp_of[i], "material": "observed", "params": {"asset": rel}})
        ledger.append(ledger_entry(f"looks like a {shape}", "inferred", rule, subject=f"p{i:04d}", confidence=conf))
    used = {o["component"] for o in ops}
    comps = [c for c in comps if c["id"] in used]

    checklist = [
        {"q": "What pieces is it made of?", "status": "answered", "by": "observed split"},
        {"q": "Which pieces repeat, and how are they laid out?",
         "status": "answered" if patterns else "answered (none found)", "by": "observed signatures"},
        {"q": "What touches what?", "status": "partly answered",
         "by": "bounding-box contact; true surface contact not computed"},
        {"q": "In what order is it assembled?", "status": "partly answered", "by": "inferred peel order"},
        {"q": "What is each part called and what does it do?", "status": "unresolved",
         "by": "run Name parts (local model) for an inferred answer"},
        {"q": "What material is each part?", "status": "unresolved",
         "by": "file materials not mapped yet; shown as neutral metal"},
    ]
    program = {"version": 1, "name": f"Reverse: {path.stem}", "units": "mm", "materials": mats,
               "components": comps, "ops": ops,
               "blueprint": {"summary": f"Reverse-engineered from {path.name}: {len(ops)} pieces in "
                                        f"{len(comps)} components.", "source": str(path)}}
    report = {"input": facts_file, "ledger": ledger, "checklist": checklist, "patterns": patterns,
              "components": comps}
    (project / "program.json").write_text(json.dumps(program, indent=1))
    (project / "reverse_report.json").write_text(json.dumps(report, indent=1))
    return program, report


def program_report(program: dict, shapes) -> dict:
    """The same ledger for a native BuildProgram: everything is observed, because the program is its own history."""
    ledger = [ledger_entry(f"{len(program['ops'])} build steps produce {len(shapes)} visible parts", "observed",
                           "the BuildProgram")]
    kinds = defaultdict(int)
    for op in program["ops"]:
        kinds[op["op"]] += 1
    ledger.append(ledger_entry("operations used: " + ", ".join(f"{k} x{v}" for k, v in sorted(kinds.items())),
                               "observed", "op census"))
    for op in program["ops"]:
        if op["op"] == "array":
            p = op.get("params", {})
            ledger.append(ledger_entry(f"{op.get('label', op['id'])}: {p.get('mode')} array of {p.get('count')}",
                                       "observed", f"op {op['id']}", subject=op["id"]))
        if op["op"] == "boolean":
            ledger.append(ledger_entry(f"{op.get('label', op['id'])}: {op['params']['mode']} of "
                                       f"{', '.join(op['inputs'])}", "observed", f"op {op['id']}", subject=op["id"]))
    checklist = [{"q": "What pieces is it made of?", "status": "answered", "by": "program"},
                 {"q": "In what order is it assembled?", "status": "answered", "by": "program step order"},
                 {"q": "How is each part made?", "status": "answered", "by": "op chain per part"}]
    return {"input": {"file": "BuildProgram", "format": "native"}, "ledger": ledger, "checklist": checklist}
