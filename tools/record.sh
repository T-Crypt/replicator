#!/bin/sh
# tools/record.sh <program.json> <cues.json> <out-dir> [WxH] [extra app args...]
# Records a preview take of the real app inside a headless gamescope (an invisible nested compositor), composited and
# rendered on the GPU named by $RECORD_VK_DEVICE (vendor:device, e.g. 8086:a780 for an Intel iGPU; default: gamescope's pick).
# CUDA is hidden; on an Intel machine only the Intel Vulkan ICD is offered.
set -eu
prog="$1"; cues="$2"; out="$3"; size="${4:-1920x1080}"; shift 3; [ $# -gt 0 ] && shift
w="${size%x*}"; h="${size#*x}"
cd "$(dirname "$0")/.."
export CUDA_VISIBLE_DEVICES=
icd=/usr/share/vulkan/icd.d/intel_icd.json
[ -f "$icd" ] && export VK_ICD_FILENAMES="$icd" VK_DRIVER_FILES="$icd"
exec gamescope --backend headless --expose-wayland ${RECORD_VK_DEVICE:+--prefer-vk-device "$RECORD_VK_DEVICE"} -W "$w" -H "$h" -w "$w" -h "$h" -r 60 -- \
    env QT_QPA_PLATFORM=wayland QSG_RENDER_LOOP=basic QSG_NO_VSYNC=1 .venv/bin/python -m replicator.app "$prog" --record "$out" --cues "$cues" --size "$size" "$@"
