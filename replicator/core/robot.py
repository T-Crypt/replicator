"""Simulator assets: a build as URDF and MJCF, one rigid link per component, with mass, centre of mass and the full
inertia tensor measured from the exact solid (physics.body), not estimated from a bounding box.

Frames: both formats are Z up, metres. A program is Y up in its own units, so every position, mesh and tensor goes
through the same +90 degree turn about X the STL and 3MF exporters apply ((x, y, z) -> (x, -z, y)). Each link's frame
is the model origin, so a link's mesh needs no offset and its inertial origin is its centre of mass.

Joints: programs carry no joints yet, so every component is welded to a massless `base` link (URDF `fixed` joints;
MJCF bodies nested under one root body with a free joint, so the model can fall and stand in a simulator). Light
effects (glow materials) have no mass; a component made only of them is left out of the inertial model but keeps
its visual mesh.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

import numpy as np
import trimesh

from . import physics
from .evaluate import Shape

__all__ = ["Link", "links", "write_urdf", "write_mjcf", "write"]

R = np.array([[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]])     # Y up -> Z up
MIN_INERTIA = 1e-9      # kg m^2: simulators reject a zero diagonal, even on a link too light to matter


@dataclass(frozen=True)
class Link:
    name: str
    label: str
    shapes: tuple[Shape, ...]
    kg: float
    com: tuple[float, float, float]                       # metres, Z up
    inertia: tuple[float, float, float, float, float, float]   # ixx, iyy, izz, ixy, ixz, iyz about the com, kg m^2


def _safe(name: str, taken: set[str]) -> str:
    base = re.sub(r"[^A-Za-z0-9_]+", "_", name).strip("_") or "part"
    if base[0].isdigit():
        base = "p_" + base
    out, n = base, 2
    while out in taken or out == "base":
        out, n = f"{base}_{n}", n + 1
    taken.add(out)
    return out


def links(program: dict, shapes: list[Shape]) -> list[Link]:
    """One link per component in build order, with its rigid-body properties in the Z-up metre frame."""
    labels = {c["id"]: c.get("label", c["id"]) for c in program.get("components", []) if isinstance(c, dict)}
    groups: dict[str, list[Shape]] = {}
    for s in shapes:
        groups.setdefault(s.component or s.id, []).append(s)
    taken: set[str] = set()
    out = []
    for cid, group in groups.items():
        b = physics.body(program, group)
        com = R @ np.asarray(b.com)
        I = R @ np.asarray(b.inertia) @ R.T
        out.append(Link(_safe(cid, taken), labels.get(cid, cid), tuple(group), b.kg,
                        tuple(float(v) for v in com),
                        (float(I[0, 0]), float(I[1, 1]), float(I[2, 2]), float(I[0, 1]), float(I[0, 2]), float(I[1, 2]))))
    return out


def _mesh(link: Link, units: str, path: Path) -> None:
    """The link's solids as one STL in metres, Z up, in the model frame."""
    s = physics.UNIT_M.get(units, 1e-3)
    parts = []
    for sh in link.shapes:
        V, F = sh.arrays()
        parts.append(trimesh.Trimesh((V.astype(np.float64) * s) @ R.T, F, process=False))
    trimesh.util.concatenate(parts).export(path)


def _inertia_ok(i: tuple) -> tuple:
    return tuple(max(v, MIN_INERTIA) for v in i[:3]) + tuple(i[3:])


def _f(v: float) -> str:
    return f"{v:.9g}"


def write_urdf(program: dict, ls: list[Link], path: Path, meshdir: str = "meshes") -> None:
    name = program.get("name", "replicator")
    out = [f'<?xml version="1.0"?>', f"<robot name={quoteattr(name)}>",
           "  <!-- Written by Replicator. Z up, metres; inertials measured from the exact solid. -->",
           '  <link name="base"/>']
    for l in ls:
        ixx, iyy, izz, ixy, ixz, iyz = _inertia_ok(l.inertia)
        mesh = f'<mesh filename="{meshdir}/{l.name}.stl"/>'
        out += [f'  <link name="{l.name}">', f"    <!-- {quoteattr(l.label)[1:-1]} -->"]
        if l.kg > 0:
            out += ["    <inertial>", f'      <origin xyz="{" ".join(_f(v) for v in l.com)}" rpy="0 0 0"/>',
                    f'      <mass value="{_f(l.kg)}"/>',
                    f'      <inertia ixx="{_f(ixx)}" ixy="{_f(ixy)}" ixz="{_f(ixz)}" iyy="{_f(iyy)}" iyz="{_f(iyz)}" izz="{_f(izz)}"/>',
                    "    </inertial>"]
        out += [f"    <visual><geometry>{mesh}</geometry></visual>",
                f"    <collision><geometry>{mesh}</geometry></collision>", "  </link>",
                f'  <joint name="{l.name}_fixed" type="fixed"><parent link="base"/><child link="{l.name}"/>'
                '<origin xyz="0 0 0" rpy="0 0 0"/></joint>']
    out.append("</robot>")
    path.write_text("\n".join(out) + "\n")


def write_mjcf(program: dict, ls: list[Link], path: Path, meshdir: str = "meshes") -> None:
    name = program.get("name", "replicator")
    out = [f"<mujoco model={quoteattr(name)}>",
           "  <!-- Written by Replicator. Z up, metres; inertials measured from the exact solid. -->",
           f'  <compiler angle="radian" meshdir="{meshdir}" inertiafromgeom="false"/>',
           "  <asset>"]
    out += [f'    <mesh name="{l.name}" file="{l.name}.stl"/>' for l in ls]
    out += ["  </asset>", "  <worldbody>",
            '    <light pos="0 0 4" dir="0 0 -1"/>',
            '    <geom name="floor" type="plane" size="0 0 0.05" rgba="0.3 0.32 0.35 1"/>',
            '    <body name="base" pos="0 0 0">', "      <freejoint/>"]
    for l in ls:
        ixx, iyy, izz, ixy, ixz, iyz = _inertia_ok(l.inertia)
        kg = l.kg if l.kg > 0 else 1e-6
        out += [f'      <body name="{l.name}">',
                f'        <inertial pos="{" ".join(_f(v) for v in l.com)}" mass="{_f(kg)}" '
                f'fullinertia="{_f(ixx)} {_f(iyy)} {_f(izz)} {_f(ixy)} {_f(ixz)} {_f(iyz)}"/>',
                f'        <geom type="mesh" mesh="{l.name}" contype="{1 if l.kg > 0 else 0}" conaffinity="{1 if l.kg > 0 else 0}"/>',
                "      </body>"]
    out += ["    </body>", "  </worldbody>", "</mujoco>"]
    path.write_text("\n".join(out) + "\n")


def write(program: dict, shapes: list[Shape], path: str | Path) -> Path:
    """Write `<stem>.urdf` or `<stem>.xml` (MJCF, by the suffix `.xml` or `.mjcf`) with a `meshes/` folder beside it.
    Returns the model file. Both formats are written from the same links, so they agree on every mass."""
    path = Path(path)
    fmt = path.suffix.lower().lstrip(".")
    if fmt not in ("urdf", "xml", "mjcf"):
        raise ValueError("simulator export needs a .urdf, .xml or .mjcf path")
    if not shapes:
        raise ValueError("nothing to export: the build has no visible parts")
    ls = links(program, shapes)
    meshes = path.parent / "meshes"
    meshes.mkdir(parents=True, exist_ok=True)
    units = program.get("units", "mm")
    for l in ls:
        _mesh(l, units, meshes / f"{l.name}.stl")
    if fmt == "urdf":
        write_urdf(program, ls, path)
    else:
        write_mjcf(program, ls, path.with_suffix(".xml") if fmt == "mjcf" else path)
    return path.with_suffix(".xml") if fmt == "mjcf" else path
