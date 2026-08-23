# Plan: workflow-native GOAL treadmill (exploration TODO)

Status: **PARKED -- exploration plan, not scheduled.** Captured 2026-08-23 from a design conversation between Wes and the lead session running `freshbooks-tools` Phase 1. Companion to `skills/new-goal-loop/` (the manual-kickoff treadmill that exists today). Owner: whoever picks this up; pilot target suggestion at the bottom.

## The idea

Today's treadmill (see `skills/new-goal-loop/SKILL.md`) needs a human to kick off each phase: clear context, paste `/goal complete everything in @GOAL.md`. The insight: **that outer loop can live inside a Claude Code dynamic workflow** (the `Workflow` tool), because a workflow script is plain JS that carries no model context -- every `agent()` call is a fresh context. "Context clear between phases" is just a `while` loop over `agent()` calls. The manual re-queue is a policy choice (human checkpoint per phase), not a technical necessity.

## Target topology: script-as-treadmill ("interpreter" pattern)

The script never hardcodes the phase list. It is a generic interpreter of GOAL.md; the queue IS the file on disk, re-read each iteration by a fresh agent. Sketch:

```js
export const meta = { name: 'goal-treadmill', description: 'Run GOAL.md phases until done/attended/budget', phases: [] }
const ledger = []
while (true) {
  // 1. A fresh agent reads GOAL.md + progress.md from disk -> typed plan
  const plan = await agent(
    "Read GOAL.md and docs/progress.md. Return the CURRENT phase as JSON: " +
    "{phase, name, branch, implModel, reviewModel, deliverables[], attended, done}",
    { schema: PLAN, phase: 'plan' })
  if (plan.done) return ledger
  if (plan.attended) return { ...ledgerSummary(), stopped: plan.phase, reason: 'attended stage -- human needed' }
  if (budget.total && budget.remaining() < PHASE_FLOOR) return { ...ledgerSummary(), stopped: plan.phase, reason: 'budget' }

  // 2. One implementer (fresh context, tier from the plan)
  const impl = await agent(implOrder(plan), { model: plan.implModel, phase: `P${plan.phase} impl` })

  // 3. Three read-only lanes in parallel, typed findings
  const lanes = await parallel(['code-review', 'simplify', 'security'].map(l =>
    () => agent(laneOrder(l, plan), { model: plan.reviewModel, schema: FINDINGS, phase: `P${plan.phase} gate` })))

  // 4. QA (the only gate runner), then fix rounds -- deterministic loop, max 5
  let qa = await agent(qaOrder(plan), { model: plan.reviewModel, schema: VERDICT, phase: `P${plan.phase} gate` })
  for (let round = 1; !clean(qa, lanes) && round <= 5; round++) {
    const triage = await agent(triageOrder(plan, lanes, qa), { model: 'fable', schema: TRIAGE, phase: `P${plan.phase} fix` })
    await agent(fixOrder(plan, triage), { model: plan.implModel, phase: `P${plan.phase} fix` })
    qa = await agent(reQaOrder(plan, triage), { model: plan.reviewModel, schema: VERDICT, phase: `P${plan.phase} fix` })
  }
  if (!clean(qa, lanes)) return { ...ledgerSummary(), stopped: plan.phase, reason: 'gate did not converge in 5 rounds' }

  // 5. Ship: merge --no-ff, push, update progress/changelogs, REWRITE GOAL.md for the next phase
  ledger.push(await agent(shipOrder(plan), { schema: SHIPPED, phase: `P${plan.phase} ship` }))
}
```

Key properties:

- **State stays on disk** (GOAL.md, progress.md, git, `docs/phases/<n>/reports/`), written by the agents as they work -- same as today. The workflow adds `journal.jsonl` + typed verdicts on top. The state machine's "accurate state as it goes" requirement is satisfied by construction.
- **Dynamic replanning falls out for free.** A mid-phase discovery becomes a new Retarget row written into GOAL.md during the run; the ship agent orders it; the next iteration's plan-reader returns whatever GOAL.md now says. The script needs zero changes to accept plan mutation. Lessons stay append-only; locked decisions stay locked (write that into the ship agent's order).
- **The gate's concurrency rules become structural.** "Only QA runs the gate" and "lanes are read-only" are enforced by the script's sequencing, not by prompt obedience.
- **Model tier rules** map to `opts.model` per call; triage is a fable-class call (or returned to the invoking session if human oversight is wanted -- see Open Questions).

## What the harness supports today (verified against the Workflow tool contract, 2026-08-23)

- `while` loops driven by data returned from `agent()` calls (schema-validated JSON) -- the interpreter pattern is fully expressible.
- Fresh context per `agent()`; `opts.model` / `opts.effort` per call; `phase()` / `opts.phase` for display grouping (dynamic titles fine; `meta.phases` is cosmetic).
- `isolation: 'worktree'` for parallel implementer batches (maps to phase-2-style batch parallelism natively).
- `resumeFromRunId`: completed `agent()` calls with unchanged (prompt, opts) replay from cache -- crash recovery across a long multi-phase run.
- Budget introspection (`budget.total/spent/remaining`) for loop guards; 1000-agent lifetime cap as a runaway backstop.
- Workflow agents have full tools (can write files, run git, SendMessage) so report files and doc updates work unchanged.

## Hard limits found (design around these)

1. **Attended stages cannot pause for a human.** Background workflow agents cannot interact with the user. The script must detect `attended` phases and RETURN cleanly ("waiting on user for X"); the human does the step, then re-invokes with `resumeFromRunId`. GOAL.md's attended flags become load-bearing data, not prose.
2. **Nesting is one level.** A workflow can `workflow()` a child; the child cannot nest further, and a workflow-spawned agent cannot launch workflows. So the phase subtree is flattened into the script (interpreter pattern), NOT "each top-level agent runs its own workflow". The alternative topology -- top-level `agent()` per phase that fans out its own gate via the `Agent` tool -- works but loses schemas, journal, resume caching, and enforced sequencing for the inner tree. Interpreter pattern preferred.
3. **Resume + mutated world.** Cache keys are (prompt, opts). Prompts embed the phase number, so cross-phase false hits cannot happen -- but resuming a run after hand-editing GOAL.md or the tree mid-phase can serve stale cached results. Rule: resume only forward; after manual intervention, start a fresh run.
4. **Implementer context is not continuable.** Fix rounds brief a FRESH agent from typed findings + diff (today's SendMessage-same-implementer continuity does not exist inside workflows). Mitigation: evidence-bearing findings; SDD's own escalation rule already uses fresh implementers at rounds 4-5. Accept the rounds-1-3 regression or route fixes back to the invoking session.
5. **Permission surface.** The run inherits the session's permission mode; an overnight run needs auto/acceptEdits plus allowlisted git/gh operations, or it stalls invisibly. Haiku-tier agents anywhere in the loop stall on prompts (no auto mode) -- same rule as the manual loop.
6. **Plugins cannot ship workflows first-class.** Named workflows resolve from built-ins and `.claude/workflows/` only. Distribution path: a skill/command in this repo carries the script (inline or as a file under the skill dir) and invokes `Workflow` -- which also satisfies the tool's explicit-opt-in requirement.
7. **Workflow size guideline** defaults to ~15 agents/run. A multi-phase overnight run blows past that; the user must raise/remove the guideline ("Dynamic workflow size" in /config) or the invocation prompt must state the intended scale.

## Oversight & guardrails (policy, decide before piloting)

- Full autonomy moves triage judgment from the human-adjacent lead into a fable `agent()`. Oversight becomes `/workflows` + TaskStop + on-disk reports instead of a conversation. That trade is the point -- but make it explicit per project.
- Guardrails to build into the script/orders: per-iteration budget floor; max-phases-per-run cap; ship agent may only append/retarget GOAL.md (never rewrite Lessons or locked decisions); gate non-convergence returns instead of looping; every return value names exactly where the run stopped and why.

## Open questions for the pilot

- Triage in-loop (fable agent) vs returned-to-session (human-reviewable between workflow invocations)? Start with returned-to-session for the first pilot, in-loop for the second.
- Where do the typed schemas (PLAN/FINDINGS/VERDICT/TRIAGE/SHIPPED) live so the manual loop's markdown reports and the workflow's JSON stay one source of truth? Likely: JSON schema files under `skills/new-goal-loop/templates/` that the markdown templates reference.
- How does the goal Stop-hook interact with a workflow that runs for hours? (Expected: fine -- background-work deferral -- but verify.)
- Does `resumeFromRunId` behave acceptably when the resumed prompt embeds file contents that changed (plan-reader prompts should embed only paths, never contents).

## Pilot plan (when picked up)

1. Toy repo first: 3 fake micro-phases, gate = a script that greps for planted defects. Verify: interpreter loop, attended-return, resume, replanning row insertion.
2. Real pilot: one LOW-RISK phase of a real treadmill repo (e.g. a docs or release-hardening phase), single iteration (`maxPhases: 1`), triage returned-to-session.
3. Compare against the manual loop on: tokens, wall-clock, convergence rounds, defects escaped to gate, lead-context size.
4. If it wins: `skills/goal-treadmill-workflow/` skill carrying the script + schemas; `new-goal-loop` gains a "workflow-native variant" section pointing at it.

## Source

Distilled from the 2026-08-23 freshbooks-tools session (Wes + lead): the "top-level nodes are fresh contexts, so the treadmill CAN be the workflow's outer loop" correction, the interpreter-not-tree realization, and the limits list verified against the Workflow tool contract that day. The manual treadmill it extends is documented in `skills/new-goal-loop/`.
