"""Replicator: you specify it, you build it."""
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent
QML = PACKAGE / "qml"              # the workspace; its materials load ../../shaders relative to qml/viewport
FIXTURES = PACKAGE / "fixtures"    # example programs, each passes tools.check; the start screen lists them
