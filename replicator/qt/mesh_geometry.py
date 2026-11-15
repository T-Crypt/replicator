"""Viewport geometry: a solid (positions + normals split at sharp edges) and its feature lines (C4D 'lines' look)."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import Property, QByteArray, QObject, Signal
from PySide6.QtGui import QColor, QVector3D
from PySide6.QtQuick3D import QQuick3DGeometry

A = QQuick3DGeometry.Attribute
SHARP_DEG = 35.0
EDGE_DEG = 28.0
MAX_EDGE_TRIS = 250_000


def mesh_arrays(m) -> tuple[np.ndarray, np.ndarray]:
    """Interleaved [x y z nx ny nz] float32 and uint32 indices."""
    mn = m.calculate_normals(0, SHARP_DEG).to_mesh()
    vp = np.asarray(mn.vert_properties, np.float32)
    tri = np.asarray(mn.tri_verts, np.uint32)
    if vp.shape[1] >= 6:
        return np.ascontiguousarray(vp[:, :6]), tri
    p = vp[:, :3][tri.reshape(-1)]
    a, b, c = p[0::3], p[1::3], p[2::3]
    n = np.cross(b - a, c - a)
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    verts = np.hstack([p, np.repeat(n, 3, axis=0)]).astype(np.float32)
    return verts, np.arange(len(p), dtype=np.uint32).reshape(-1, 3)


def feature_edges(V: np.ndarray, F: np.ndarray) -> np.ndarray:
    """Line segments [k, 2, 3] along creases sharper than EDGE_DEG and open boundaries (welded by position)."""
    if len(F) == 0 or len(F) > MAX_EDGE_TRIS:
        return np.zeros((0, 2, 3), np.float32)
    P = V[:, :3]
    key = np.round(P / (np.ptp(P, axis=0).max() * 1e-6 + 1e-12)).astype(np.int64)
    _, weld = np.unique(key, axis=0, return_inverse=True)
    Fw = weld.reshape(-1)[F]
    a, b, c = (P[F[:, i]] for i in range(3))
    fn = np.cross(b - a, c - a)
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-12
    e = np.concatenate([Fw[:, [0, 1]], Fw[:, [1, 2]], Fw[:, [2, 0]]])
    eraw = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    face = np.tile(np.arange(len(F)), 3)
    es = np.sort(e, axis=1)
    order = np.lexsort((es[:, 1], es[:, 0]))
    es, face, eraw = es[order], face[order], eraw[order]
    same = np.all(es[1:] == es[:-1], axis=1)
    keep = []
    i, n = 0, len(es)
    cos_t = np.cos(np.radians(EDGE_DEG))
    idx = np.nonzero(same)[0]
    paired = np.zeros(n, bool)
    paired[idx] = True
    paired[idx + 1] = True
    # boundaries: edges with no partner
    keep.append(eraw[~paired])
    # creases: partner faces whose normals differ by more than EDGE_DEG
    sharp = idx[np.einsum("ij,ij->i", fn[face[idx]], fn[face[idx + 1]]) < cos_t]
    keep.append(eraw[sharp])
    E = np.concatenate(keep) if keep else np.zeros((0, 2), np.uint32)
    return np.ascontiguousarray(P[E].astype(np.float32))


class EdgeGeometry(QQuick3DGeometry):
    def __init__(self, data: QByteArray, lo, hi):
        super().__init__()
        self.setVertexData(data)
        self.setStride(12)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Lines)
        self.addAttribute(A.Semantic.PositionSemantic, 0, A.ComponentType.F32Type)
        self.setBounds(QVector3D(*lo), QVector3D(*hi))
        self.update()


class MeshGeometry(QQuick3DGeometry):
    """One leaf shape. phase: 0 static, 1 arriving (materialize), 2 leaving (dematerialize, reverse playback).

    The bridge caches these per shape, but Qt Quick 3D draws a geometry object only for the first Model that adopts
    it: once that Model is destroyed (every step change rebuilds the Repeater3D delegates) a new Model holding the same
    object renders nothing, and update() does not bring it back. So the cache keeps the computed buffers and
    `for_step` hands each step a fresh object built from them (cheap: the byte arrays are shared, not recomputed)."""
    changed = Signal()

    def __init__(self, shape, material: dict | None, phase: int, comp_color: str, comp_label: str, _from=None):
        super().__init__()
        if _from is not None:                       # a fresh Qt object over another one's buffers
            self.__dict__.update({k: v for k, v in _from.__dict__.items() if k.startswith("_") or k == "materialName"})
        else:
            self._id, self._label, self._part, self._comp = shape.id, shape.label, shape.part, shape.component
            self.materialName = ""
            self._comp_color = QColor(comp_color)
            self._comp_label = comp_label
            self._offset = QVector3D(0, 0, 0)
            mat = material or {}
            c = mat.get("base_color", [0.72, 0.73, 0.76])
            e = mat.get("emissive", [0, 0, 0])
            self._color = QColor.fromRgbF(*[min(max(float(x), 0.0), 1.0) for x in c[:3]])
            self._emissive = QColor.fromRgbF(*[min(max(float(x), 0.0), 1.0) for x in e[:3]])
            self._metal = float(mat.get("metalness", 0.0))
            self._rough = float(mat.get("roughness", 0.5))
            self._opacity = min(max(float(mat.get("opacity", 1.0)), 0.05), 1.0)
            verts, tri = mesh_arrays(shape.manifold)
            self._tris = len(tri)
            self._lo, self._hi = verts[:, :3].min(0), verts[:, :3].max(0)
            self._vbytes = QByteArray(verts.tobytes())
            self._ibytes = QByteArray(tri.astype(np.uint32).tobytes())
            self._ebytes = QByteArray(np.ascontiguousarray(feature_edges(verts, tri).reshape(-1, 3)).tobytes())
        self._phase = phase
        self.setVertexData(self._vbytes)
        self.setIndexData(self._ibytes)
        self.setStride(24)
        self.setPrimitiveType(QQuick3DGeometry.PrimitiveType.Triangles)
        self.addAttribute(A.Semantic.PositionSemantic, 0, A.ComponentType.F32Type)
        self.addAttribute(A.Semantic.NormalSemantic, 12, A.ComponentType.F32Type)
        self.addAttribute(A.Semantic.IndexSemantic, 0, A.ComponentType.U32Type)
        self.setBounds(QVector3D(*self._lo.tolist()), QVector3D(*self._hi.tolist()))
        self.update()
        self._edges = EdgeGeometry(self._ebytes, self._lo.tolist(), self._hi.tolist())

    def for_step(self, phase: int) -> "MeshGeometry":
        """A new Qt geometry object over these cached buffers, for the next step's delegate."""
        return MeshGeometry(None, None, phase, "", "", _from=self)

    def set_offset(self, v) -> None:
        self._offset = QVector3D(*v)

    def _ro(t):  # noqa: N805
        return lambda f: Property(t, f, constant=True)

    @_ro(str)
    def shapeId(self): return self._id
    @_ro(str)
    def label(self): return self._label
    @_ro(str)
    def part(self): return self._part
    @_ro(str)
    def component(self): return self._comp
    @_ro(str)
    def componentLabel(self): return self._comp_label
    @_ro(QColor)
    def componentColor(self): return self._comp_color
    @_ro(int)
    def phase(self): return self._phase
    @_ro(bool)
    def fresh(self): return self._phase == 1
    @_ro(QColor)
    def baseColor(self): return self._color
    @_ro(QColor)
    def emissive(self): return self._emissive
    @_ro(float)
    def metalness(self): return self._metal
    @_ro(float)
    def roughness(self): return self._rough
    @_ro(float)
    def opacity(self): return self._opacity
    @_ro(float)
    def minY(self): return float(self._lo[1])
    @_ro(float)
    def maxY(self): return float(self._hi[1])
    @_ro(QVector3D)
    def center(self): return QVector3D(*((self._lo + self._hi) / 2).tolist())
    @_ro(QVector3D)
    def explodeOffset(self): return self._offset
    @_ro(int)
    def triangles(self): return self._tris
    @_ro(QObject)
    def edges(self): return self._edges
