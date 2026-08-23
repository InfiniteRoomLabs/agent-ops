# Work order: implementer

Dispatch: `Agent(subagent_type: "general-purpose", model: "<per the Retarget table>", name: "phase-<n>-impl")`. Fill every `<...>`. Pointers, not pasted text.

---

You are implementing **Phase <n> (<name>)** of `<project>`. Work ONLY inside `<absolute repo or worktree path>` on branch `<branch>` (already created, clean). Do not touch other branches or worktrees.

## Read first (pointers, not pasted)

1. The oracle: `<spec path>` sections <list>. Section <k> is locked; do not redesign.
2. Conventions: `CLAUDE.md`, `GOAL.md` stage 2 for this phase (the deliverable list and acceptance criteria).
3. **Ground truth before coding:** <the external docs/API pages/code the phase is built against, with URLs or paths>. Read them before writing code; they carry details the spec summarizes.
4. Exemplar to mirror in shape and style: `<path to the most recently shipped phase's code + tests>`.

## Deliverables

- <file or package> -- <exactly what it must contain>
- Tests: <unit expectations>; <integration expectations for every cross-package seam this phase introduces>. Coverage >= <n>%. <race/strict flags> clean.
- Doc comments on every exported/public member; changelog `[Unreleased]` entry in the existing style.
- `<gate command>` green on a clean tree. Always run tooling via `<mise run ...|...>`.
- Commit on `<branch>` in TDD-sized conventional commits (`feat(<scope>): ...`), each green. **Stage and commit in separate tool calls.** Do NOT push, do NOT merge -- the lead runs the gate and ships.

## Gotchas (these cost prior runs time)

- <project-specific traps from CLAUDE.md Gotchas + GOAL.md Lessons relevant to this phase>
- If the spec is wrong about something the oracle does, implement what the oracle does, add a `> **STATE AS OF <date>**` callout in the affected spec section in the same commit, and list the discrepancy in your report.
- <If public repo:> fixture IDs and names are synthetic; never paste real IDs, tokens, or names.

## Reporting (both channels)

When done (gate green, committed, `git status --porcelain` empty): write the report to `docs/phases/<n>/reports/implementer.md` (commit it), send the same report with `SendMessage` to `team-lead` (report in `message`, not `summary`), AND return it as your final text. Report: files created/changed, test counts, coverage, the exact gate tail, `git log --oneline main..<branch>`, `git status --porcelain` output, and every spec discrepancy or ambiguity you hit and how you resolved it. If you are genuinely blocked, report the blocker the same way instead of guessing.
