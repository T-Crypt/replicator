"""Optional voice: Replicator reads an explanation aloud, and you can dictate a dream.

Nothing here loads a model in this process or touches the RTX card. Speech comes from a server you already run
(any OpenAI-compatible `/v1/audio/speech`, such as Kokoro-FastAPI) or from espeak-ng on the CPU; dictation goes to
an OpenAI-compatible `/v1/audio/transcriptions` server or to a local command such as whisper.cpp's `whisper-cli`.
Child processes get an environment with every GPU hidden. Audio is recorded and played through PipeWire.
"""
from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import tempfile
import urllib.request
import uuid
from pathlib import Path

CPU_ENV = {"CUDA_VISIBLE_DEVICES": "", "NODE_LLAMA_CPP_GPU": "false"}
TMP = Path(tempfile.gettempdir()) / "replicator-voice"


def _env() -> dict:
    return {**os.environ, **CPU_ENV}


def status(cfg: dict) -> dict:
    """What is usable right now, in words the Preferences panel can show."""
    tts = ("Kokoro / OpenAI-compatible server" if cfg.get("tts_url") else
           "espeak-ng (CPU, robotic; set a speech server for a natural voice)" if shutil.which("espeak-ng") else "")
    stt = ("transcription server" if cfg.get("stt_url") else
           "local command" if cfg.get("stt_cmd") and shutil.which(shlex.split(cfg["stt_cmd"])[0]) else "")
    return {"tts": tts, "stt": stt, "play": bool(shutil.which("pw-play") or shutil.which("paplay")),
            "record": bool(shutil.which("pw-record") or shutil.which("arecord"))}


def synthesize(text: str, cfg: dict) -> Path:
    """Text -> a WAV file. Raises RuntimeError with the reason when no voice is available."""
    TMP.mkdir(parents=True, exist_ok=True)
    out = TMP / f"say-{uuid.uuid4().hex[:10]}.wav"
    if cfg.get("tts_url"):
        body = {"model": "kokoro", "input": text, "voice": cfg.get("tts_voice") or "af_heart",
                "response_format": "wav"}
        req = urllib.request.Request(cfg["tts_url"].rstrip("/") + "/v1/audio/speech", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                out.write_bytes(r.read())
            return out
        except OSError as e:
            raise RuntimeError(f"speech server unreachable ({e})") from None
    if shutil.which("espeak-ng"):
        subprocess.run(["espeak-ng", "-s", "165", "-w", str(out), text], check=True, env=_env(), timeout=60)
        return out
    raise RuntimeError("no voice: set a speech server in Preferences or install espeak-ng")


def player(wav: Path) -> subprocess.Popen:
    cmd = ["pw-play", str(wav)] if shutil.which("pw-play") else ["paplay", str(wav)]
    return subprocess.Popen(cmd, env=_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def recorder() -> tuple[subprocess.Popen, Path]:
    """Start recording the default microphone (16 kHz mono). Stop it with .terminate()."""
    TMP.mkdir(parents=True, exist_ok=True)
    wav = TMP / f"mic-{uuid.uuid4().hex[:10]}.wav"
    if shutil.which("pw-record"):
        cmd = ["pw-record", "--rate", "16000", "--channels", "1", str(wav)]
    elif shutil.which("arecord"):
        cmd = ["arecord", "-q", "-f", "S16_LE", "-r", "16000", "-c", "1", str(wav)]
    else:
        raise RuntimeError("no recorder (pw-record or arecord)")
    return subprocess.Popen(cmd, env=_env(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL), wav


def transcribe(wav: Path, cfg: dict) -> str:
    if cfg.get("stt_url"):
        boundary = uuid.uuid4().hex
        parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\nwhisper-1\r\n'.encode(),
                 f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="mic.wav"\r\n'
                 f'Content-Type: audio/wav\r\n\r\n'.encode(), wav.read_bytes(), f"\r\n--{boundary}--\r\n".encode()]
        req = urllib.request.Request(cfg["stt_url"].rstrip("/") + "/v1/audio/transcriptions", b"".join(parts),
                                     {"Content-Type": f"multipart/form-data; boundary={boundary}"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return str(json.load(r).get("text", "")).strip()
        except OSError as e:
            raise RuntimeError(f"transcription server unreachable ({e})") from None
    if cfg.get("stt_cmd"):
        cmd = [a.replace("{wav}", str(wav)) for a in shlex.split(cfg["stt_cmd"])]
        r = subprocess.run(cmd, capture_output=True, text=True, env=_env(), timeout=180)
        if r.returncode:
            raise RuntimeError(f"transcription command failed: {r.stderr.strip()[-200:]}")
        return " ".join(r.stdout.split())
    raise RuntimeError("dictation is not set up: add a transcription server or command in Preferences")
