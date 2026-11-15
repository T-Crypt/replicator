"""Dictation on the CPU with faster-whisper: a WAV in, the words on stdout. Replicator's `stt_cmd` runs it in the
venv that has faster-whisper (here ~/ext/whisper-cpu), with every GPU hidden and the model read from the local cache:

    ~/ext/whisper-cpu/bin/python tools/transcribe.py {wav} [--model small.en]

The WAV is read with the standard library (faster-whisper's own decoder breaks on some PyAV builds).
"""
from __future__ import annotations

import argparse
import os
import sys
import wave

os.environ["CUDA_VISIBLE_DEVICES"] = ""
os.environ.setdefault("HF_HUB_OFFLINE", "1")


def pcm16k(path: str):
    import numpy as np
    with wave.open(path) as w:
        rate, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise SystemExit(f"{path}: expected 16-bit PCM, got {8 * width}-bit")
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    if ch > 1:
        a = a.reshape(-1, ch).mean(1)
    if rate != 16000:   # linear resample; dictation does not need better
        a = np.interp(np.arange(0, len(a), rate / 16000), np.arange(len(a)), a).astype(np.float32)
    return a


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("wav")
    ap.add_argument("--model", default="small.en")
    a = ap.parse_args()
    from faster_whisper import WhisperModel
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(pcm16k(a.wav), language="en", vad_filter=True)
    print(" ".join(s.text.strip() for s in segs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
