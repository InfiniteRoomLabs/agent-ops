# CLAUDE.md sections for a treadmill repo (merge into the repo's CLAUDE.md)

Keep the repo's own intro/toolchain/key-locations content; these are the treadmill-specific sections. Fill `<...>`.

## Read-first

- **`docs/progress.md`** -- living status. Always read before starting work; update at every phase boundary.
- **`GOAL.md`** -- the current autonomous phase goal + full roadmap. This repo runs on the `/goal` treadmill: `/goal complete everything in @GOAL.md` ships one phase and retargets the file.
- **The spec** (`<spec path>`) -- section <k> is locked (do not re-litigate); read only the sections the current phase needs.

## Working conventions

- **Phases, not tasks.** One GOAL block = one phase = one branch `phase-<n>/<slug>` = one gate = one `--no-ff` merge. Parallel batches (if any) run as worktrees under `.worktrees/` (gitignored); everything else is in-place branches.
- **Four-lane review gate before every merge:** code review, simplification, security (parallel, read-only) then QA (the only lane that runs `<gate command>`). Templates in `docs/phases/_templates/`. Reports land in `docs/phases/<n>/reports/<lane>.md` and via `SendMessage` to `team-lead`. One fix commit, re-gate, merge.
- **Model rules (non-negotiable):** pass `model:` explicitly on every dispatch; reviewers are one tier above the implementer (sonnet -> opus, opus -> fable); haiku only for read-only sweeps that cannot hit a permission prompt. Check an agent's `tools:` before writing its prompt; `general-purpose` has everything.
- **Green rule:** tests first where feasible; no skipped/focused/silenced tests without an issue link; lint warnings are errors; `<race/strict flags>` always; coverage floor **<n>%** enforced by the gate.
- **Inferred vs confirmed:** facts about the oracle are CONFIRMED / INFERRED / TODO. When reality disagrees with the spec, reality wins -- add a `> **STATE AS OF YYYY-MM-DD**` callout in the affected spec section in the same commit.
- **Commits:** conventional, imperative, scoped. **Stage and commit in separate tool calls** (version guard); never `-a`/`-am`, never `--no-verify`. On `main`, `CHANGELOG.md` must be staged (changelog guard -- a Claude hook, not a git hook). Co-author trailer per harness rules.
- **Changelogs:** Keep a Changelog, `[Unreleased]` on top<; per-module changelogs if multiple release artifacts>.
- <If public:> **Public-repo hygiene on every commit:** no vault item names, internal IPs/domains, real tenant/account IDs, tokens, or personal correspondents. Fixtures synthetic. Secret wiring (`fnox.toml` etc.) gitignored.
- **Docs are ASCII-only and never hard-wrapped.**

## If you break something

- Gate red: read the first failing step's output; run the gate's sub-tasks individually to isolate.
- Hook blocked a commit: it is doing its job; check what you staged -- do not bypass.
- Fresh session disoriented: `docs/progress.md` has the ledger and the how-to-resume checklist.
