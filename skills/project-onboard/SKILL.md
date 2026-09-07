---
name: project-onboard
description: Use when setting up a new repository or bringing an existing one up to Infinite Room Labs conventions -- routes to the template-repo cut-and-fill flow for new repos, applies the harness/toolchain delta to existing ones, and hands off to /new-goal-loop.
tags:
  function: [engineering, operations]
  scenario: [project-setup]
  custom: [onboarding, conventions, marketplace, template-repo]
---

# Project Onboard

A router, not a scaffolder. The canonical layout lives in `InfiniteRoomLabs/template-repo` and is tested there; this skill never re-implements it.

## 1. New repo

1. Cut it from `InfiniteRoomLabs/template-repo` ("Use this template" on GitHub, or `gh repo create <org>/<name> --template InfiniteRoomLabs/template-repo --private`).
2. Follow the checklist in the new repo's `README.md`, section "Using this template": replace the six placeholders, pin the toolchain in `mise.toml`, fill the gate steps in `scripts/check.sh`, describe the system in `docs/architecture/model.c4`, `mise run arch:gen`, truncate `CHANGELOG.md`, delete the section.
3. `mise install && mise run check` must be green before the first push.
4. Run `/new-goal-loop <what you are building>`.

## 2. Existing repo

Apply the delta by copying from a fresh clone of `template-repo`; do not hand-author these:

- `.claude/settings.json` (marketplaces + default plugins + `enabledMcpjsonServers`) and `.claude/.gitignore`; then the `.gitignore` allowlist lines (`.claude/*`, `!.claude/.gitignore`, `!.claude/settings.json`) and secret/tool wiring ignores (`fnox.toml`, `mise.local.toml`, `.env*`, `.envrc`, `.worktrees/`).
- `.claudeignore` (must not blanket-ignore `.claude/`).
- `mise.toml` (merge into an existing one: keep the repo's tools, add `[tasks.check]` and the `arch:*` tasks) and `scripts/check.sh`, `scripts/arch-gen.sh`, `scripts/redaction-check.sh`.
- `docs/architecture/` (config + `spec.c4`/`model.c4`/`views.c4`) and `.mcp.json`.
- `CHANGELOG.md` (Keep a Changelog, `[Unreleased]` on top) and `LICENSE` if missing.
- Merge the template's `CLAUDE.md` sections (First run, Toolchain, Working conventions, Architecture, Gotchas) into the repo's own, keeping its project-specific content. Add the thin `AGENTS.md` Codex pointer.

Then `mise run check` green, and `/new-goal-loop` to install the treadmill.

## Do not

- Duplicate the treadmill artifacts (GOAL.md, `docs/phases/_templates/`, `docs/progress.md`); `skills/new-goal-loop/templates/` is their only source.
- Blanket-ignore `.claude/` -- that hides load-bearing settings and hooks (reversed in infra 2026-08-27).
- Add configuration the project does not need yet, install dependencies, or write a placeholder README.
