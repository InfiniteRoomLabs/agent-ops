---
name: arch-sync
description: Use at the end of a phase (before the QA lane) or after any structural refactor to reconcile the LikeC4 architecture model in docs/architecture/ with the code, regenerate the committed diagrams, and stage the result. Reports code-vs-model gaps as a heuristic; never edits the model without confirmation.
allowed-tools: Read, Glob, Grep, Bash, Edit, Write
tags:
  function: [engineering]
  scenario: [architecture, review-gate, phase-close]
  custom: [likec4, architecture-as-code, treadmill]
---

# Arch Sync

Reconcile the LikeC4 model (`docs/architecture/*.c4`) with the code that changed this phase, then regenerate and stage the committed diagrams. The gate (`mise run check`) proves the model is well-formed and the diagrams are current; this command is the step that asks whether the model is still **true**.

## When

- End of every phase, before dispatching the QA lane.
- After any structural refactor: a service, datastore, queue, or external dependency added, removed, or re-wired.
- On demand: `/arch-sync`.

## Steps

1. **Find the structural changes.** `git diff --name-only main...HEAD` (or the phase's base). Group the changed paths by the top-level directories and packages they touch. Ignore docs, tests, and generated files.
2. **Read the model.** `read-project-summary` via the `likec4` MCP server (falls back to reading `docs/architecture/*.c4` if the server is not available). Note every element's FQN, kind, and `technology`.
3. **Report gaps, both directions.** List (a) changed code paths with no plausible element (new directories, new binaries, new integrations named in imports or config) and (b) elements whose code path no longer exists. Mark the whole list as a **heuristic**: a path-to-element match is a guess, not a proof. Do not edit anything yet.
4. **Propose model edits** as a diff against `docs/architecture/model.c4` (and `spec.c4` if a new kind is needed, `views.c4` if a new view earns its place). Each proposed element carries `technology` and a one-line `description`; each new relationship carries a label. Ask for confirmation.
5. **Apply the confirmed edits**, then `mise run arch:fmt`, `mise run arch:validate`.
6. **Regenerate:** `mise run arch:gen`. This rewrites `docs/architecture/generated/*.mmd` and the landscape block in `docs/architecture/README.md`.
7. **Stage:** `git add docs/architecture`. Do not commit; the phase's own commit (or the fix commit after the gate) carries it. Say what was staged.

## Rules

- Never `git commit` here, and never run the gate; the QA lane owns `mise run check`.
- A finding in step 3 is evidence for a question, not a verdict. Say "no element covers `cli/internal/backup/`" -- do not say "the model is wrong".
- If step 1 shows no structural change, say so in one line and stop. An empty sync is a valid outcome.
- Tag colors in `spec.c4` take hex or `rgb()`/`rgba()` only; element `style { color ... }` takes the semantic tokens (`primary`, `gray`, ...). Mixing them up fails `likec4 validate`.
- Keep the model at the granularity of "things that can fail independently or be owned separately". A helper package is not an element.
