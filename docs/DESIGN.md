# Replicator: design review and direction (2026-11-13)

## The vision, restated

Replicator is a studio for objects made with local models: describe a thing, watch it assemble, take it apart, learn
how it works, show it off, and one day print it. The reference is a professional DCC (dense, fast, keyboard
driven), but the first minute must need no manual: one prompt field, one search box, obvious modes.

Three rules shape every decision:
1. **One document.** The BuildProgram is the only source of truth; every panel is a view of it.
2. **Evidence is labelled.** Observed, inferred, unknown in Reverse; cited, measured, concept in Explain. A guess
   is never drawn as a fact.
3. **The card belongs to the models.** Replicator never loads a model itself; GPU work goes to the user's model
   server or ComfyUI, and the window draws on the iGPU when there is one beside a discrete card.

## What the review found

| # | Finding | Change | State |
|---|---|---|---|
| 1 | Colours, sizes and fonts were hard-coded in every file; one fixed look; the mono font name was wrong | A token module (`Replicator.UI/Theme.qml`): 4 themes, 6 accents, 3 densities, motion switch, saved | Done |
| 2 | Tool icons were font glyphs that changed with the system font | A vector icon set drawn from SVG paths (`Icon.qml`), tinted by token | Done |
| 3 | Each command was written three times (menu, shortcut, button) and most had no shortcut | One action registry in `Main.qml` feeds menus, shortcuts and the Commander (`Ctrl+K`), which also opens builds, switches themes, paints materials and sends a typed sentence to the model | Done |
| 4 | An empty app showed a bare grid | A start screen: the prompt in the centre, four ways in, examples and recent builds | Done |
| 5 | The grid was the loudest thing on screen and shimmered at the horizon | An adaptive decimal grid that keeps a steady line count at any zoom and fades at grazing angles; themed backdrop with a vignette | Done |
| 6 | The kernel was fast but silent, and every edit re-evaluated the whole program on a cold cache to validate it | Edits validate on the shared cache; caches are bounded; the status bar shows step, parts, triangles, size, rebuild time and cache hits; redo | Done |
| 7 | Materials could only be typed as JSON | A material library (27 PBR presets) and a shelf that paints a part or a whole component as one undo step | Done |
| 8 | Image to 3D had no visual link to its source pictures | Reference sheets stand around the model at its measured height, paper keyed out, visible only from the model's side | Done |
| 9 | Reverse listed what a model is made of but never how it works | Explain: a bounded web research lane, a local model, and a checker that keeps a sentence only if it is cited, measured, or (for concepts) marked as concept; Present mode plays it | Backend done, UI in HANDOFF |
| 10 | `qml/` was one flat folder and `bridge.py` one object | `Replicator/UI`, `panels/`, `viewport/`; new Python features live in their own modules. Splitting `bridge.py` itself is next | Partly done |

## Structure

```
qml/Replicator/UI/   tokens, icons and controls (a QML module; no panel logic)
qml/panels/          one file per dock or overlay; talks to `studio` only
qml/viewport/        the 3D view, its materials and overlays
qml/Main.qml         layout, workspace state, the action registry
replicator/core/     program, kernel, assembly, reverse, explain, materials (no Qt)
replicator/research/ the web lane (no Qt, no model)
replicator/llm/      prompts and the local-model client
replicator/qt/       the bridge between core and QML
replicator/voice.py  optional speech in and out (subprocesses, CPU only)
replicator/config.py optional services file (outside the repo)
```

Rules: a panel never hard-codes a colour; a new command is one entry in `actions`; `core/` and `research/` import
no Qt, so they are testable without a window.

## Explain, precisely

1. The model proposes 3 or 4 search queries for the real mechanisms closest to the object.
2. The lane reads at most 6 pages and passes on at most 6,400 characters of ranked excerpts, numbered.
3. The model writes chapters whose sentences are `cited` (with a source number), `measured` or `concept`.
4. `core/explain.verify` checks each one: a cited sentence must share vocabulary with the excerpt it cites; a
   measured sentence may only contain numbers Replicator measured; concept sentences are allowed only for concepts.
   Failures are dropped for real objects and shown as concept for concepts.
5. A concept opens with a notice that it is fictional, then still explains what it would be and how it would work.

Guaranteed: nothing is shown as cited without a matching excerpt. Not guaranteed: that the source is right or that
a paraphrase kept every nuance, which is why the sources are listed and clickable. Research is off until the
user turns it on; only search words leave the machine. With research on, a dream is grounded the same way: the
blueprint stage receives the excerpts and records which real mechanism each part follows.

## Roadmap

See [ROADMAP.md](ROADMAP.md).
