"""A QQuick3DGeometry filled from a manifold: positions + normals (split at sharp edges), Y-up, ready for a Model."""
from __future__ import annotations

import numpy as np
from manifold3d import Manifold
from PySide6.QtCore import Property, QByteArray, Signal
from PySide6.QtGui import QColor, QVector3D
from PySide6.QtQuick3D import QQuick3DGeometry

A = QQuick3DGeometry.Attribute
SHARP_DEG = 35.0


def mesh_arrays(m: Manifold) -> tuple[np.ndarray, np.ndarray]:
    """Interleaved [x y z nx ny nz] float32 and uint32 indices. Normals are smooth across faces that meet at under
    SHARP_DEG and split across sharper edges, so a revolved nozzle reads round and a box reads crisp."""
    mn = m.calculate_normals(0, SHARP_DEG).to_mesh()
    vp = np.asarray(mn.vert_properties, np.float32)
    tri = np.asarray(mn.tri_verts, np.uint32)
    if vp.shape[1] >= 6:
        verts = np.ascontiguousarray(vp[:, :6])
    else:  # flat fallback
        p = vp[:, :3][tri.reshape(-1)]
        a, b, c = p[0::3], p[1::3], p[2::3]
        n = np.cross(b - a, c - a)
        n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
        verts = np.hstack([p, np.repeat(n, 3, axis=0)]).astype(np.float32)
        tri = np.arange(len(p), dtype=np.uint32).reshape(-1, 3)
    return verts, tri


class MeshGeometry(QQuick3DGeometry):
    changed = Signal()

    def __init__(self, shape_id: str, label: str, part: str, material: dict | None, m: Manifold, fresh: bool):
        super().__init__()
        self._id, self._label, self._part, self._fresh = shape_id, label, part, fresh
        mat = material or {}
        c = mat.get("base_color", [0.72, 0.73, 0.76])
        e = mat.get("emissive", [0, 0, 0])
        self._color = QColor.fromRgbF(*[float(x) for x in c[:3]])
        self._emissive = QColor.fromRgbF(*[float(x) for x in e[:3]])
        self._metal = float(mat.get("metalness", 0.0))
        self._rough = float(mat.get("roughness", 0.5))
        verts, tri = mesh_arrays(m)
        self._tris = len(tri)
        lo, hi = verts[:, :3].min(0), verts[:, :3].max(0)
        self._lo, self._hi = lo, hi
        self.setVertexData(QByteArray(verts.tobytes()))
        self.setIndexData(QByteArray(tri.astype(np.uint32).tobytes()))
        self.setStride(24)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        self.addAttribute(A.Semantic.PositionSemantic, 0, A.ComponentType.F32Type)
        self.addAttribute(A.Semantic.NormalSemantic, 12, A.ComponentType.F32Type)
        self.addAttribute(A.Semantic.IndexSemantic, 0, A.ComponentType.U32Type)
        self.setBounds(QVector3D(*lo.tolist()), QVector3D(*hi.tolist()))
        self.update()

    def _ro(t):  # noqa: N805 - small helper for read-only Qt properties
        return lambda f: Property(t, f, constant=True)

    @_ro(str)
    def shapeId(self): return self._id
    @_ro(str)
    def label(self): return self._label
    @_ro(str)
    def part(self): return self._part
    @_ro(bool)
    def fresh(self): return self._fresh
    @_ro(QColor)
    def baseColor(self): return self._color
    @_ro(QColor)
    def emissive(self): return self._emissive
    @_ro(float)
    def metalness(self): return self._metal
    @_ro(float)
    def roughness(self): return self._rough
    @_ro(float)
    def minY(self): return float(self._lo[1])
    @_ro(float)
    def maxY(self): return float(self._hi[1])
    @_ro(int)
    def triangles(self): return self._tris
