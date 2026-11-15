"""Task modules: NAME, CLASS (spec or function), CATEGORY and instance(seed)."""
from . import board, flange, house, lamp

TASKS = {m.NAME: m for m in (flange, board, house, lamp)}

__all__ = ["TASKS", "board", "flange", "house", "lamp"]
