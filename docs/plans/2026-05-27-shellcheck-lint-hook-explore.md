# Explore: shellcheck linting for Claude Code (LSP and/or PostToolUse hook)

Status: EXPLORATION PROMPT (not a committed plan). Pick this up in a fresh session.

## The itch

While editing shell scripts in another repo, a missing `shellcheck` binary meant
lint feedback only happened when manually run. Agents write a lot of `*.sh`
(installers, hooks, deploy scripts). We want shellcheck findings surfaced
automatically, the moment a `.sh` file is written/edited -- not discovered later.

## Two angles to investigate

### 1. Does a shellcheck LSP already exist for Claude Code?
- Claude Code supports LSP integrations. Is there an existing shellcheck-backed
  language server (e.g. `bash-language-server`, which shells out to shellcheck)?
- `bash-language-server` is the obvious candidate -- it integrates shellcheck
  diagnostics. Investigate whether Claude Code can consume it and whether that
  gives inline diagnostics during agent edits, not just in an IDE.
- Decision: adopt existing (bash-language-server + shellcheck) vs. nothing fits.

### 2. PostToolUse hook for `*.sh` in agent-ops (the cheap win)
- Add a `PostToolUse` hook matching `Write|Edit` where the file path ends in
  `.sh` (and maybe `.bash`). Run `shellcheck` on the edited file; surface
  findings back to the agent as hook output.
- Pattern already exists: see `hooks/hooks.json` + the existing
  `pre-deploy-secrets-sync.sh` / `post-deploy-secrets-verify.sh` for the shape.
- Open questions:
  - Hard dependency: is `shellcheck` installed on dev machines? Hook should
    degrade gracefully (skip + warn) if absent, not block edits.
  - Severity gating: warn-only vs. block on errors? Probably warn-only (info to
    the agent), never block -- shellcheck has false positives (SC2015 etc.).
  - Scope: agent-ops only, or a reusable hook other repos can install via the
    marketplace? Leans toward a marketplace-distributable hook.
  - Output shape: how do PostToolUse hooks feed text back to the agent? Confirm
    the JSON contract (`additionalContext`?) so findings actually reach the model.

## Suggested first step
Prototype angle 2 (PostToolUse + shellcheck) -- it's a few lines and immediately
useful. Then evaluate angle 1 (bash-language-server LSP) as the richer,
inline-diagnostics upgrade if the hook proves valuable.

## Reference
Idea surfaced 2026-05-27 while building the claudesync cookie-harvest broker
(`scripts/lib/harvest-cookie.sh`), where shellcheck caught an SC2015 nit that
would otherwise have shipped.
