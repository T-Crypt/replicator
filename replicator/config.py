"""Optional services, kept outside the repo in ~/.config/Replicator/services.json (mode 600).

Everything here is off until the operator turns it on in Preferences:
  research     bool   Explain and grounded dreams may look things up on the web (only search words leave the machine)
  search_url   str    a SearXNG instance for the wider web; empty = Wikipedia only
  speak        bool   read explanations aloud
  tts_url      str    an OpenAI-compatible speech server (Kokoro-FastAPI: http://host:8880); empty = espeak-ng
  tts_voice    str    voice name for that server
  stt_url      str    an OpenAI-compatible transcription server (faster-whisper-server, whisper.cpp server)
  stt_cmd      str    or a local command, "{wav}" is replaced by the recording (for example: whisper-cli -m model.bin -f {wav} -nt)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PATH = Path(os.environ.get("REPLICATOR_SERVICES", Path.home() / ".config" / "Replicator" / "services.json"))
DEFAULTS = {"research": False, "search_url": "", "speak": False, "tts_url": "", "tts_voice": "af_heart",
            "stt_url": "", "stt_cmd": ""}


def load() -> dict:
    cfg = dict(DEFAULTS)
    try:
        data = json.loads(PATH.read_text())
        cfg.update({k: v for k, v in data.items() if k in DEFAULTS and isinstance(v, type(DEFAULTS[k]))})
    except (OSError, ValueError):
        pass
    return cfg


def save(cfg: dict) -> None:
    PATH.parent.mkdir(parents=True, exist_ok=True)
    PATH.write_text(json.dumps({k: cfg.get(k, v) for k, v in DEFAULTS.items()}, indent=1))
    PATH.chmod(0o600)
