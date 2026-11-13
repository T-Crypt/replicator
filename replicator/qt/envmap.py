"""A procedural studio HDRI (equirectangular, RGBA32F) for the light probe: a soft grey dome, a bright overhead
soft box, two strip lights and a warm floor bounce. Metals need something to reflect; this is it, made locally."""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QByteArray, QSize
from PySide6.QtQuick3D import QQuick3DTextureData


def studio_hdri(w: int = 1024, h: int = 512) -> np.ndarray:
    u = (np.arange(w) + 0.5) / w
    v = (np.arange(h) + 0.5) / h
    phi = (u * 2 - 1) * np.pi                 # longitude
    theta = (0.5 - v) * np.pi                 # latitude, +pi/2 = up
    P, T = np.meshgrid(phi, theta)
    up = np.sin(T)
    sky = np.clip(up, 0, 1)
    col = np.zeros((h, w, 3), np.float32)
    col += (0.55 + 0.35 * sky)[..., None] * np.array([0.92, 0.95, 1.0])           # dome
    col += (np.clip(-up, 0, 1) ** 0.6)[..., None] * np.array([0.38, 0.34, 0.30])  # floor bounce
    col *= np.where(up < 0, 0.6, 1.0)[..., None]
    # overhead soft box
    box = np.exp(-((T - 1.25) / 0.18) ** 2) * np.exp(-(P / 0.55) ** 2)
    col += (box * 9.0)[..., None]
    # two vertical strip lights, left and right of the key
    for c, s in ((-1.9, 5.0), (1.6, 3.5)):
        strip = np.exp(-((P - c) / 0.07) ** 2) * (np.abs(T - 0.25) < 0.55)
        col += (strip * s)[..., None]
    rgba = np.concatenate([col, np.ones((h, w, 1), np.float32)], axis=2)
    return np.ascontiguousarray(rgba[::-1])    # Qt textures start at the bottom row


class EnvMap(QQuick3DTextureData):
    def __init__(self):
        super().__init__()
        img = studio_hdri()
        self.setSize(QSize(img.shape[1], img.shape[0]))
        self.setFormat(QQuick3DTextureData.Format.RGBA32F)
        self.setHasTransparency(False)
        self.setTextureData(QByteArray(img.tobytes()))
