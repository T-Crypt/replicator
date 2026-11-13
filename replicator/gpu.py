"""The 4090 belongs to llama-swap and Berth (operator rule, ~/.claude/CLAUDE.md). Replicator draws on the Intel iGPU.

`pinned_env()` is applied before Qt loads: Mesa's EGL/GLX vendor (iris on the UHD 770, real hardware, not llvmpipe),
only the Intel Vulkan ICD, CUDA hidden. `on_nvidia(pid)` asks nvidia-smi whether a PID holds the card anyway; the app
checks itself after the first frame and quits if it does. `software=True` is the test-harness variant (llvmpipe).
"""
from __future__ import annotations

import os
import subprocess

MESA_EGL = "/usr/share/glvnd/egl_vendor.d/50_mesa.json"
INTEL_ICD = "/usr/share/vulkan/icd.d/intel_icd.json"


def pinned_env(software: bool = False) -> dict[str, str]:
    env = {
        "QSG_RHI_BACKEND": "opengl",
        "__EGL_VENDOR_LIBRARY_FILENAMES": MESA_EGL,
        "__GLX_VENDOR_LIBRARY_NAME": "mesa",
        "VK_ICD_FILENAMES": INTEL_ICD,
        "VK_DRIVER_FILES": INTEL_ICD,
        "CUDA_VISIBLE_DEVICES": "",
        "NODE_LLAMA_CPP_GPU": "false",
        "QT_FFMPEG_DECODING_HW_DEVICE_TYPES": ",",
        "QT_FFMPEG_ENCODING_HW_DEVICE_TYPES": ",",
    }
    if software:
        env.update({"LIBGL_ALWAYS_SOFTWARE": "1", "GALLIUM_DRIVER": "llvmpipe",
                    "VK_ICD_FILENAMES": "/dev/null", "VK_DRIVER_FILES": "/dev/null"})
    return env


def apply(software: bool = False) -> None:
    os.environ.update(pinned_env(software))


def nvidia_pids() -> set[int]:
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return set()
    pids = {int(x) for x in out.split() if x.strip().isdigit()}
    try:  # graphics (G) clients appear only in the plain table (Holodeck harness_env.gpu_pids, same parse)
        full = subprocess.run(["nvidia-smi"], capture_output=True, text=True, timeout=10).stdout
        for line in full.splitlines():
            parts = line.split()
            if len(parts) > 4 and parts[0] == "|" and parts[4].isdigit():
                pids.add(int(parts[4]))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return pids


def on_nvidia(pid: int | None = None) -> bool:
    return (pid or os.getpid()) in nvidia_pids()
