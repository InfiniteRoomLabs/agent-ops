# AGENTS.md -- agent-ops (for Codex)

Read `~/.codex/AGENTS.md` (global) and `./CLAUDE.md` (this repo) first. `CLAUDE.md`
is the authoritative brief and applies to you too.

## What this repo is

The Claude Code marketplace for Infinite Room Labs (open source, MIT) and the
**source of truth** for every agent, skill, command, and hook the org uses. If
you are creating, modifying, or reasoning about agent tooling anywhere on this
machine, start here.

- `registry.yaml` -- full index of active agents/skills/commands with tags.
- `agents/{division}/*.md` -- agent definitions (frontmatter: description,
  model, tools, color, tags + system prompt).
- `skills/*/SKILL.md`, `commands/*.md`.
- `CLAUDE.md` -- marketplace conventions, tagging system, plugin structure.

## Codex notes

- This is a Claude Code marketplace; components are authored for Claude Code's
  agent/skill/command/hook model. When porting a pattern to Codex, translate the
  mechanism (e.g. Claude Code hooks -> Codex equivalents) rather than copying
  verbatim.
- A planned cross-platform feature will keep CLAUDE.md and AGENTS.md (and Codex
  support generally) in sync across the marketplace. Until it lands, keep this
  file and `CLAUDE.md` consistent by hand.

Keep this AGENTS.md and `CLAUDE.md` in sync: change a convention in one, change it
in both.
