# Progress

Living status doc. Read first, update at every phase boundary. Last updated: <date>.

## Current state

- <bullets: what exists, what is merged, spec status, credentials/tooling wired>

## Phase ledger

| Phase | Status | Branch / merge | Notes |
|---|---|---|---|
| <n> <name> | not started | in progress | SHIPPED `<sha>` | `phase-<n>/<slug>` | <notes> |

## Discoveries

- <date>: <discovery that changed the plan or the spec, with pointer to the STATE AS OF callout>

## Next action

<one sentence: the exact next command or decision>

## How to resume in a fresh session

1. Read this file, then `GOAL.md`, then `CLAUDE.md`.
2. `git status --porcelain` must be empty and `git log --oneline -5` should match the ledger above. If not, reconcile before starting.
3. Read only the spec sections the current phase names.
4. Start the goal.
