# GOAL.md -- autonomous next-phase goal

Run with `/goal complete everything in @GOAL.md`. Each run ships exactly one phase of `<project>` through the pipeline: verify premise -> implement -> four-lane review gate -> merge -> ship -> retarget this file. The design oracle is `<spec path>` (the "spec"); `CLAUDE.md` holds the conventions and dispatch rules; `docs/progress.md` is where we are.

**Shipped so far:** <nothing yet | running ledger: phase, merge sha, one-line lesson>. Next default target: **Phase <n> (<name>)**. Full roadmap in *Retarget* at the bottom.

---

## Goal (current target: Phase <n> -- <name>)

> **Goal -- don't stop until Phase <n> (<name>) ships:**
>
> 1. **Verify the premise before building.** Read the spec sections <list> and `CLAUDE.md`. Confirm: <the concrete assertions this phase depends on -- tool versions resolvable, external facts still true, upstream phase actually delivered what its report claimed>. Anything wrong: fix the spec with a `> **STATE AS OF YYYY-MM-DD**` callout in the affected section, note it in `docs/progress.md`, and continue.
> 2. **Implement** on branch `phase-<n>/<slug>` by dispatching ONE implementer (`general-purpose`, `model: "<sonnet|opus>"`, work order from `docs/phases/_templates/implementer.md`, pointers to spec sections <list>). Deliverables, each with an acceptance criterion:
>    - <deliverable> -- <acceptance criterion>
>    - Acceptance: <gate command> green in <scope> on a clean tree.
> 3. **Four-lane gate** -- dispatch code-review, simplification, and security lanes in parallel (read-only), then the QA lane (the only lane that runs the gate); all `general-purpose`, **`model: "<one tier above implementer>"`**. Work orders from `docs/phases/_templates/`. Reports to `docs/phases/<n>/reports/<lane>.md` AND via `SendMessage` to `team-lead`. Triage, ONE fix commit `fix(<slug>): apply the review-gate findings`, re-run the gate, confirm `git status --porcelain` is empty.
> 4. **Ship** -- merge `phase-<n>/<slug>` into `main` with `--no-ff` (body summarises gate results); update `CHANGELOG.md` + `docs/progress.md`; push; confirm CI green. Then **retarget THIS file to Phase <n+1>** (see *Self-advance*) and commit it with the docs.
>
> **Done when:** <phase-specific done criteria>, CI green, the gate green locally on a clean tree, `docs/progress.md` + changelogs updated, **and `GOAL.md` retargeted to Phase <n+1>.** **Also done when** the `## Blocked on user` section below names one concrete action only the user can take and the lead has committed it and stopped -- a parked attended step is a clean exit, not a failure. **Stop only** for that, for a genuine decision you + an advisor skill cannot confidently make, or for a permission the harness will not grant.
>
> **When blocked on the user:** write the action under `## Blocked on user`, commit, say so once, and stop **without any further tool calls** (no polling the remote, no status re-prints -- the goal hook treats tool use as progress and re-prompts every few seconds). Never poll for a human.

## Blocked on user

<empty when nothing is parked. When the lead needs the user: one line per action, exact command or click, and what unblocks it. The next `/goal` run reads this first, verifies the action landed, empties the section, and continues.>

### Self-advance (do this as the last Ship step, every run)

Leave `GOAL.md` pointed at the **next** phase so the following `/goal` run is paste-ready:
- Update **"Shipped so far"** and strike the shipped row in the **Retarget table** (mark `SHIPPED`, add merge sha + one-line lesson).
- Rewrite the **`## Goal` heading + block** for the next phase: stage 1 verifies that phase's premise; stage 2 names the branch, implementer model (from the Retarget table), work-order template, and concrete deliverables with acceptance criteria; stage 3 is the gate with the reviewer model one tier above; stage 4 is ship + retarget.
- Append anything you learned to **Lessons** (process traps only -- feature notes go in `docs/progress.md` and spec callouts).
- **Advance only within the approved roadmap.** If the next row in *Approved roadmap* exists, rewrite the `## Goal` block for it. If it does not, the roadmap is exhausted: write the maintenance/park block below instead of inventing a phase.
- Any follow-on work the lanes surfaced this run goes under *Proposed (needs user approval)*, not into the approved roadmap. It runs only after the user approves it (which moves it up into *Approved roadmap*).
- **Next approved phase after Phase <n>: <the next Approved-roadmap row, or "none -- park">.**

### Parking when the roadmap is exhausted

When no approved phase remains, replace the `## Goal` block with a park block: state that the approved roadmap is done, list the *Proposed* rows (each waiting on the user to approve or on an attended input), and set **Done when** to "the user has approved a proposed row (moved it into *Approved roadmap*) and rewritten this block into that phase, or decided none runs." Mark it **Blocked on user**. A `/goal` run that lands here reads `## Blocked on user`, sees nothing approved changed, and stops after one turn with no tool call.

---

## Lessons from prior runs (read before starting)

<seed from templates/seed-lessons.md; append-only thereafter>

## Reference

- **Spec:** `<spec path>`. Section <k> is locked; sections <list> are the build oracle; section <k> is this process.
- **Conventions + dispatch rules:** `CLAUDE.md`. **Status:** `docs/progress.md`.
- **Work orders:** `docs/phases/_templates/{implementer,code-review,simplify,security,qa}.md`. Phase artifacts: `docs/phases/<n>/reports/`.
- **Oracle / ground truth:** <the external docs, API, binary, or dataset the project is built against, with URLs or paths>.
- **Toolchain:** everything through `<mise run ...|make ...|...>`. `<gate command>` is the gate.
- **Exemplars to mirror:** within this repo, the most recently shipped phase. Outside: <reference codebases for shape and conventions>.

## Retarget / roadmap

### Approved roadmap

The phases the user signed off. This is the ceiling: the loop runs these and stops. One row per phase; strike and mark `SHIPPED` as they land. "Attended" means the lead should have the user available. Adding a row here requires the user's approval -- the lead may reorder these but never append a new one on its own.

| Phase | Branch | Implementer -> Reviewers | Effort | Notes |
|---|---|---|---|---|
| **<n> <name>** | `phase-<n>/<slug>` | <impl> -> <reviewer> | <trivial|low|med|high> | <scope; attended?> |

**Batch option:** <phases that may run together in one attended run, if any>.

### Proposed (needs user approval)

Follow-on work the review lanes surfaced mid-run. The lead writes rows here freely; the loop does **not** run them. Each stays here until the user promotes it into *Approved roadmap*. When the approved roadmap is exhausted and this list is non-empty, the run parks (see *Parking when the roadmap is exhausted*) rather than promoting one itself.

| Proposed phase | Why (surfaced by) | Effort | Attended? |
|---|---|---|---|
| <name> | <lane + finding that raised it> | <trivial|low|med|high> | <yes/no> |
