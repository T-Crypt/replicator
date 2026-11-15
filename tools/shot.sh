#!/bin/sh
# tools/shot.sh <program.json | ""> <out.png> [WxH] [cue ...]
# One frame of the real, exposed window inside a headless gamescope (tools/record.sh). Unlike --shot, which grabs a
# hidden window that lays out only during the grab, overlays projected from the 3D view (callouts, read-outs) and
# narrow-window layouts come out exactly as on screen. Each cue is a QML expression run 0.3 s in; the frame is taken
# at 3.5 s. Needs gamescope.
set -eu
prog="$1"; out="$2"; size="${3:-1760x1020}"; shift 2; [ $# -gt 0 ] && shift
command -v gamescope >/dev/null || { echo "tools/shot.sh needs gamescope; use --shot instead" >&2; exit 2; }
cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
python3 - "$tmp/cues.json" "$@" <<'PY'
import json, sys
json.dump([[0.3, c] for c in sys.argv[2:]] + [["end", 3.5]], open(sys.argv[1], "w"))
PY
sh tools/record.sh "$prog" "$tmp/cues.json" "$tmp/frames" "$size" --fps 4 >/dev/null 2>&1
last="$(ls "$tmp"/frames/*.jpg | tail -1)"
.venv/bin/python -c "import sys; from PySide6.QtGui import QImage; QImage(sys.argv[1]).save(sys.argv[2])" "$last" "$out"
echo "saved $out"
