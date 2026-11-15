"""Optional services, kept outside the repo in services.json (mode 600): ~/.config/Replicator/services.json on Linux,
or wherever $REPLICATOR_SERVICES points.

Everything here is off until the operator turns it on in Preferences:
  research     bool   Explain and grounded dreams may look things up on the web (only search words leave the machine)
  search_url   str    a SearXNG instance for the wider web; empty = Wikipedia only
  speak        bool   read explanations aloud
  tts_url      str    an OpenAI-compatible speech server (Kokoro-FastAPI: http://host:8880); empty = espeak-ng
  tts_voice    str    voice name for that server or command
  tts_cmd      str    or a local command; {text}, {wav} and {voice} are filled in (no shell), e.g. Kokoro's tts.py on CPU
  stt_url      str    an OpenAI-compatible transcription server (faster-whisper-server, whisper.cpp server)
  stt_cmd      str    or a local command, "{wav}" is replaced by the recording (for example: whisper-cli -m model.bin -f {wav} -nt)
  printers     list   saved printer profiles: catalog ids ("bambu_x1c", ...) or custom dicts
                      {"id", "name", "vendor", "bed_x", "bed_y", "height", "nozzle", "margin", "transport"} (core/printers.py)
  active_printer str  the id of the printer prints are gated on; empty = no printer (exports stay printer-less)
  endpoints    list   more model engines, each {"name", "url", "model", "key_env"}: any OpenAI-compatible server
                      (a lab's checkpoint on vLLM, Ollama, a hosted API). key_env names the environment variable that
                      holds the API key; the key itself never goes in this file. Example:
                      {"name": "lab-ft", "url": "http://192.168.1.40:8000/v1", "model": "cad-ft-7b", "key_env": ""}
                      An entry may add "chat_template_kwargs" (a dict sent as-is, e.g. {"reasoning_effort": "high"}).
  default_engine str  the engine Specify, Edit and Explain use; empty = "local" (replicator/llm/client.py)
"""
from __future__ import annotations

import json
import os
from pathlib import Path

PATH = Path(os.environ.get("REPLICATOR_SERVICES", Path.home() / ".config" / "Replicator" / "services.json"))
DEFAULTS = {"research": False, "search_url": "", "speak": False, "tts_url": "", "tts_voice": "af_heart",
            "tts_cmd": "", "stt_url": "", "stt_cmd": "", "endpoints": [], "printers": [], "active_printer": "",
            "default_engine": ""}


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
