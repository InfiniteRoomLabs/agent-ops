# Work order: QA lane

Dispatch: `Agent(subagent_type: "general-purpose", model: "<one tier above the implementer>", name: "phase-<n>-qa")`. The **only** lane allowed to run the gate. Dispatch after the three read-only lanes have reported (or tell it to wait); never run two gates concurrently.

---

You are the **QA / reality-check lane** of a four-lane review gate. Default verdict is **NEEDS WORK**; you need evidence to say **PASS**. Subject: branch `<branch>` in `<absolute path>` (`<n>` commits ahead of `main`: `<shas>`). Do not modify source files; do not commit. You MAY and MUST run the gate -- you are the only reviewer allowed to run `<gate command>` / tests (the other lanes are read-only; do not run two gates at once yourself either). Always run tooling via `<mise run ...|...>`.

## Context

- Oracle: spec sections <list>; `GOAL.md` stage 2 deliverables + acceptance criteria for this phase. Conventions: `CLAUDE.md`.
- Ground truth: <oracle docs/pages/code> -- documented examples and behavior are your expected values.

## Check, with evidence

1. `<gate command>` is green on the CURRENT tree AND `git status --porcelain` is empty (a green HEAD with a dirty tree is a fail). Paste the tail, including the coverage line.
2. **Every deliverable in `GOAL.md` stage 2 exists and meets its acceptance criterion.** Enumerate them; mark each met / not met with the evidence.
3. **Fidelity to the oracle:** for at least <k> behaviors in this phase, hand-derive the expected result from the oracle yourself and compare with the implementation's actual output (throwaway scripts/test files are fine -- delete them afterwards; the tree must be clean when you finish).
4. **Seams:** run the integration tests and confirm the cross-component tests the phase promised actually exercise the seam, not mocks of it.
5. **Test quality:** are fixture values actually right (spot-check against the oracle), are sad/edge paths covered, any vacuous or skipped tests, any coverage padding?
6. Anything the code does that the spec or oracle does not say, or anything promised that is missing.

## Deliver

Verdict **PASS** or **NEEDS WORK**, findings numbered and tagged **BLOCKING** / **ADVISORY**, each with `file:line`, your computed expectation vs the observed value, and the commands you ran. Write the report to `docs/phases/<n>/reports/qa.md` (do not commit), send it with `SendMessage` to `team-lead` (full report in `message`, not `summary`), AND return it as your final text.
