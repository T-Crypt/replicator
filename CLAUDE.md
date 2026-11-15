# Replicator: how to work here

**Every session and every task in this repo runs in poteto-mode** (operator, 2026-11-14).

1. At the start of a session read `.claude/skills/poteto-mode/SKILL.md` in full.
2. For each task pick its playbook (`.claude/skills/poteto-mode/playbooks/<name>.md`: session-pickup, feature,
   bug-fix, investigation, refactoring, ...) and copy its steps into the todo list.
3. Before applying a principle, read its leaf `.claude/skills/principle-<name>/SKILL.md` in full. In the reply,
   name only the principles you actually read and the choice each one changed.
4. Prose (replies, README, docs, commit messages) goes through `.claude/skills/unslop`; docs and commit messages
   also through `.claude/skills/technical-writing`.
5. Subagents follow the global rule: local llama-swap roles first, Claude subagents only when a local role is not
   good enough, and say why.

The skills are vendored from `~/.agents/skills` so they travel with the repo; refresh them from there.

@AGENTS.md
