"""Dream -> blueprint -> BuildProgram, on local models only (llama-swap :9090 or Strata :8080).

Engines: "dirk" (Dirk-27B, default, reasoning xhigh), "coder"/"agent" (NInfer roles), "strata" (Strata :8080,
only while it is the resident engine). Nothing here talks to a cloud model.
"""
from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

from ..core.evaluate import EvalError, Evaluator
from ..core.program import OPS, VERSION, validate

PROMPTS = Path(__file__).parent / "prompts"
ENGINES = {
    "dirk": ("http://127.0.0.1:9090/v1/chat/completions", "dirk", {"reasoning_effort": "xhigh"}),
    "coder": ("http://127.0.0.1:9090/v1/chat/completions", "coder", None),
    "agent": ("http://127.0.0.1:9090/v1/chat/completions", "agent", None),
    "strata": ("http://127.0.0.1:8080/v1/chat/completions", "strata", None),
}
REPAIR_ROUNDS = 2


def chat(messages: list[dict], engine: str = "dirk", max_tokens: int = 14000, timeout: int = 900) -> str:
    url, model, kwargs = ENGINES[engine]
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.6}
    if kwargs:
        body["chat_template_kwargs"] = kwargs
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.load(r)
    return data["choices"][0]["message"]["content"] or ""


def extract_json(text: str):
    """The last ```json fence, else the outermost {...}/[...] in the reply."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S)
    fences = re.findall(r"```(?:json)?\s*\n(.*?)```", text, flags=re.S)
    for cand in reversed(fences):
        try:
            return json.loads(cand)
        except json.JSONDecodeError:
            continue
    for opener, closer in (("{", "}"), ("[", "]")):
        i, j = text.find(opener), text.rfind(closer)
        if 0 <= i < j:
            try:
                return json.loads(text[i:j + 1])
            except json.JSONDecodeError:
                pass
    raise ValueError("no JSON found in the model reply")


def _prompt(name: str, **fill) -> str:
    s = (PROMPTS / f"{name}.md").read_text()
    for k, v in fill.items():
        s = s.replace("{{" + k + "}}", v)
    return s


def op_reference() -> str:
    from ..core import program as P
    lines = []
    for name, (req, opt) in OPS.items():
        kind = "primitive" if name in P.PRIMITIVES else "modifier (one input)" if name in P.MODIFIERS \
            else "combiner (inputs: 2+)"
        lines.append(f"- {name}: {kind}; required {sorted(req) or '-'}; optional {sorted(opt) or '-'}")
    return "\n".join(lines)


def problems(program) -> list[str]:
    if not isinstance(program, dict):
        return ["the reply must be one JSON object (the BuildProgram)"]
    program.setdefault("version", VERSION)
    errs = validate(program)
    if errs:
        return errs
    try:
        Evaluator().step(program)
    except EvalError as e:
        return [str(e)]
    return []


def dream(prompt: str, engine: str = "dirk", log=print) -> dict:
    """Text in, a validated BuildProgram out (its blueprint stage kept under program["blueprint"])."""
    log(f"blueprint: asking {engine}")
    bp = extract_json(chat([{"role": "user", "content": _prompt("blueprint", REQUEST=prompt)}], engine))
    log(f"blueprint: {len(bp.get('parts', []))} parts, {bp.get('dimensions')}")
    msgs = [{"role": "user", "content": _prompt("program", REQUEST=prompt, BLUEPRINT=json.dumps(bp, indent=1),
                                               OPS=op_reference())}]
    for rnd in range(REPAIR_ROUNDS + 1):
        log(f"program: round {rnd + 1}")
        reply = chat(msgs, engine)
        try:
            prog = extract_json(reply)
            errs = problems(prog)
        except ValueError as e:
            prog, errs = None, [str(e)]
        if not errs:
            prog["blueprint"] = bp
            log(f"program: valid, {len(prog['ops'])} ops")
            return prog
        log(f"program: {len(errs)} problems: {errs[:3]}")
        msgs += [{"role": "assistant", "content": reply},
                 {"role": "user", "content": "That program has these problems. Fix every one and reply with the "
                  "complete corrected program as one ```json block.\n- " + "\n- ".join(errs[:20])}]
    raise ValueError(f"no valid program after {REPAIR_ROUNDS + 1} rounds: {errs[:5]}")


def edit(program: dict, instruction: str, engine: str = "dirk", log=print) -> list[dict]:
    """A text edit ("longer thrusters") as an RFC 6902 patch over the program. Caller applies it."""
    from ..core.program import apply_patch
    msgs = [{"role": "user", "content": _prompt("edit", PROGRAM=json.dumps(program, indent=1),
                                               INSTRUCTION=instruction, OPS=op_reference())}]
    for rnd in range(REPAIR_ROUNDS + 1):
        log(f"edit: round {rnd + 1}")
        reply = chat(msgs, engine)
        try:
            patch = extract_json(reply)
            if not isinstance(patch, list):
                raise ValueError("the reply must be a JSON array of RFC 6902 operations")
            new = apply_patch(program, patch)
            errs = problems(new)
        except Exception as e:  # jsonpatch raises several types; all go back to the model
            patch, errs = None, [str(e)]
        if not errs:
            return patch
        msgs += [{"role": "assistant", "content": reply},
                 {"role": "user", "content": "That patch fails: " + "; ".join(errs[:10]) +
                  ". Reply with a corrected JSON Patch array in one ```json block."}]
    raise ValueError(f"no valid edit: {errs[:5]}")
