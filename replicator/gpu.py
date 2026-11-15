"""Which GPU the window draws on. On a machine with an Intel iGPU beside an NVIDIA card, the card is left to the model
server (llama.cpp, vLLM, Ollama): a viewport holding a few hundred MB of VRAM can stop a large model from loading.

`REPLICATOR_GPU` picks the policy, read before Qt loads:
  auto  (default) pin to the iGPU when both an Intel Vulkan ICD and nvidia-smi are present, otherwise leave it to Qt
  igpu  always pin to the Intel/Mesa iGPU
  any   never pin; Qt picks
When pinned, the app checks nvidia-smi for its own PID after the first frame and quits if it landed on the card
anyway. `software=True` (the test harness, `--software`) draws with Mesa's llvmpipe on the CPU.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

MESA_EGL = "/usr/share/glvnd/egl_vendor.d/50_mesa.json"
INTEL_ICD = "/usr/share/vulkan/icd.d/intel_icd.json"


def policy() -> str:
    p = os.environ.get("REPLICATOR_GPU", "auto").strip().lower()
    return p if p in ("auto", "igpu", "any") else "auto"


def should_pin() -> bool:
    p = policy()
    if p == "any":
        return False
    if p == "igpu":
        return True
    return Path(INTEL_ICD).exists() and shutil.which("nvidia-smi") is not None


def pinned_env(software: bool = False, pin: bool | None = None) -> dict[str, str]:
    pin = should_pin() if pin is None else pin
    env = {"QSG_RHI_BACKEND": "opengl", "CUDA_VISIBLE_DEVICES": ""}
    if pin:
        env.update({
            "__EGL_VENDOR_LIBRARY_FILENAMES": MESA_EGL,
            "__GLX_VENDOR_LIBRARY_NAME": "mesa",
            "VK_ICD_FILENAMES": INTEL_ICD,
            "VK_DRIVER_FILES": INTEL_ICD,
            "QT_FFMPEG_DECODING_HW_DEVICE_TYPES": ",",
            "QT_FFMPEG_ENCODING_HW_DEVICE_TYPES": ",",
        })
    if software:
        env.update({"LIBGL_ALWAYS_SOFTWARE": "1", "GALLIUM_DRIVER": "llvmpipe"})
        if pin:
            env.update({"VK_ICD_FILENAMES": "/dev/null", "VK_DRIVER_FILES": "/dev/null"})
    return env


def apply(software: bool = False) -> bool:
    """Set the environment before Qt loads; True when the window is pinned to the iGPU."""
    pin = should_pin()
    os.environ.update(pinned_env(software, pin))
    return pin


def nvidia_pids() -> set[int]:
    try:
        out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"],
                             capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        return set()
    pids = {int(x) for x in out.split() if x.strip().isdigit()}
    try:  # graphics (G) clients appear only in the plain table
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
