---
name: new-goal-loop
description: Set up the GOAL.md treadmill in a repo -- a planning session that produces a locked design spec, a phase roadmap, and the artifacts (GOAL.md, CLAUDE.md sections, progress doc, four-lane review-gate work orders) needed to run autonomous phases via `/goal complete everything in @GOAL.md`. Use when starting a project that should be built phase-by-phase by subagents with review gates, or when retrofitting that process onto an existing repo.
argument-hint: "<project or goal description>"
tags:
  function: [engineering]
  scenario: [project-bootstrap, autonomous-development]
  custom: [goal-treadmill, review-gate, sdd]
---

# /new-goal-loop

Install the **GOAL.md treadmill**: a development loop where the user kicks off each phase with `/goal complete everything in @GOAL.md` in a fresh context, the agent (the "lead") ships exactly one phase through a review gate, and the last act of every phase rewrites GOAL.md to point at the next one. Proven on `hoyle-re` (6 shipped phases) and `freshbooks-tools`. The reference implementations are those two repos; this skill is self-contained and does not require reading them.

**Templates:** `templates/` next to this file holds skeletons for every artifact. Copy, then fill every `<...>` placeholder. Do not invent your own structure when a template exists.

## The system in one paragraph

One GOAL block = one phase = one branch = one review gate = one `--no-ff` merge. The lead does judgment work inline (planning, triage, merges, GOAL rewrites) and dispatches subagents for implementation and review: one implementer, then three parallel read-only review lanes (code review, simplification, security), then a QA lane that is the only agent allowed to run the build/test gate. Findings come back as evidence-tagged reports; the lead triages, one fix commit lands, the gate re-runs, the branch merges. State lives in files (GOAL.md, docs/progress.md, git), never in anyone's context, so any fresh session can resume from disk.

## Part 1 -- the planning session (do this WITH the user, before any artifact)

Run this as a conversation, not a form. Use `superpowers:brainstorming` (architectural path) if available.

1. **Search before build.** Find existing tools/libraries that already solve the problem. Present the best 2-3 with a recommendation. Only proceed on an explicit decision to build. Record the "why build" in the spec.
2. **Verify load-bearing external facts yourself** (API behavior, SDK versions, auth flows, license terms). Never design against a search-result summary; fetch the primary source. Mark each fact CONFIRMED / INFERRED / TODO.
3. **Ask the project-shaping questions one at a time**, max 2 options each with a recommended default. Typical set: repo topology, naming/module paths, docs strategy, state/secret ownership, what to cut (YAGNI). Skip anything the user already answered; never re-ask.
4. **Write the design spec** to `docs/superpowers/specs/YYYY-MM-DD-<project>-design.md`. Required sections: Purpose (incl. why build vs adopt); **Decisions locked (do not re-litigate)** as a table with Why column; verified external facts; architecture per component; testing/CI/release design; **Process** (this loop, phase table, model table); Future Work. Self-review for placeholders/contradictions, then get the user's explicit approval of the written spec.
5. **Break the work into phases** (Part 2) and get the roadmap approved.

## Part 2 -- phases

- A phase is a **vertical slice or a coherent layer** shippable through one gate in one autonomous run. Size so the implementer's work fits one focused dispatch; split volume work into parallel batches (worktrees) only when the shared surface was pre-declared in an earlier phase so batches are purely additive.
- **Phase 0 is always scaffold**: repo layout, toolchain pins, the gate command (`mise run check` or equivalent: format + vet/typecheck + lint + tests + coverage floor + build, ending with a dirty-tree banner), CI, release plumbing, doc stubs. The gate must be green from Phase 0 on.
- Every phase row in the roadmap carries: branch name, implementer model -> reviewer model, effort rating, **attended?** flag (anything needing the user live: consent screens, credentials, first public release), and one-line scope.
- **Model rules (non-negotiable):** pass `model:` explicitly on every dispatch. Reviewers are at least one tier above the implementer (sonnet -> opus, opus -> fable/highest). Judgment-heavy phases get an opus-class implementer; pattern-following phases with a written work order get sonnet. haiku only for read-only sweeps that can never hit a permission prompt (it has no auto mode and will stall the run).

## Part 3 -- artifacts to generate (checklist)

Copy from `templates/`, fill placeholders, commit before the first `/goal` run:

- [ ] `GOAL.md` <- `templates/GOAL.template.md`. Phase 0 as the live goal block; full roadmap in the Retarget table; Lessons section seeded from `templates/seed-lessons.md` (process traps that recur everywhere -- keep them).
- [ ] Repo `CLAUDE.md` <- merge `templates/CLAUDE-sections.template.md` (read-first, working conventions, model/dispatch rules, gotchas, key locations). Keep it project-specific; the treadmill sections come from the template.
- [ ] `docs/progress.md` <- `templates/progress.template.md`. The handoff artifact: current state, phase ledger, discoveries, next action, how-to-resume.
- [ ] `docs/phases/_templates/{implementer,code-review,simplify,security,qa}.md` <- the five work orders in `templates/`. Genericize any `<oracle>` placeholders to the project's source of truth (API docs, spec, decompilation, RFC...).
- [ ] `CHANGELOG.md` (Keep a Changelog, `[Unreleased]` on top; per-module changelogs if the repo releases multiple artifacts). The agent-ops changelog guard blocks `main` commits without it staged -- note in the README that contributors need agent-ops installed.
- [ ] The spec (Part 1) committed under `docs/superpowers/specs/`.

## Part 4 -- process rules the lead must enforce every phase

**The loop:** verify premise -> implement -> [code review || simplify || security] -> QA -> triage -> ONE fix commit -> re-gate -> merge `--no-ff` -> ship -> self-advance GOAL.md.

- **Stage 1 is always "verify the premise".** Re-check what this phase's goal block asserts (against the oracle/docs/code) before building. When reality disagrees with the spec, reality wins: fix the spec in the same run with a `> **STATE AS OF YYYY-MM-DD**` callout in the affected section.
- **Dispatch traps** (each has burned a real run):
  1. Model tiers are pinned in agent definitions -- omit `model:` and you silently get the pin. Always pass it.
  2. Check the agent's `tools:` list before writing its prompt; most curated review agents lack `Bash` or `SendMessage` and fail silently. `general-purpose` works for every lane.
  3. Tell every subagent HOW to deliver: `SendMessage` to `team-lead` (NOT `main`) with the full report in `message` (not `summary`), AND write the report to `docs/phases/<n>/reports/<lane>.md`, AND return it as final text.
- **Only the QA lane runs the gate.** The other three lanes are read-only (`git`, `grep`, read); concurrent gate runs corrupt shared build/coverage outputs. QA's default verdict is NEEDS WORK; evidence required for PASS; a green HEAD with a dirty tree (`git status --porcelain`) is a fail.
- **Verdict vocabulary:** QA `PASS|NEEDS WORK`; code review `APPROVE|REQUEST CHANGES`; simplify `APPLY-RECOMMENDED|OPTIONAL|DO-NOT-APPLY`; security `PASS|BLOCK`. Findings numbered, tagged BLOCKING/ADVISORY, each with `file:line` + evidence. Lead overrides are allowed and recorded in the merge commit body. Refuse simplifications that change observable behavior.
- **Green rule:** no skipped/focused/silenced tests without an issue link; lint warnings are errors; race/strict modes always on; coverage floor enforced by the gate, not by promises.
- **Commit discipline:** conventional, imperative, scoped. Stage and commit in SEPARATE tool calls (version guard). Changelog staged with every `main` commit (changelog guard). Never `--no-verify`. `--no-ff` merges with the gate summary in the body. Co-author trailer per harness rules.
- **Knowledge capture, triple-recorded:** process traps -> GOAL.md Lessons + repo CLAUDE.md Gotchas + project memory. Feature/API discoveries -> `docs/progress.md` + spec `STATE AS OF` callouts. Facts carry CONFIRMED/INFERRED/TODO status.
- **Public-repo hygiene** (if public): no vault item names, internal hostnames/IPs, real tenant/account IDs, tokens, or personal names in any commit -- fixtures synthetic, secret wiring (e.g. `fnox.toml`) gitignored.
- **Token-cost controls:** brief agents with file pointers, not pasted bulk; reports go to files; one gate runner; exemplar-to-mirror instead of long style prose; a short honest report is a valid outcome.

## Part 5 -- running and advancing

- Kick off each phase in a fresh context: `/goal complete everything in @GOAL.md`. The goal block must end with "**and GOAL.md retargeted to the next phase**" inside its Done-when, and "**Stop only** for a genuine decision you + an advisor skill cannot confidently make".
- **Self-advance is the last ship step, every run:** update "Shipped so far", strike the Retarget row (add merge sha + one-line lesson), rewrite the `## Goal` block for the next phase (stage 1 = verify premise; stage 2 = branch + implementer model + work-order template + deliverables with acceptance criteria; stage 3 = gate with reviewer tier one up; stage 4 = ship + retarget), append Lessons.
- **Mid-run replanning is legitimate:** a discovered gap becomes a new Retarget row (with effort + attended flag) written during the run; the roadmap is append-and-reorder, but Lessons are append-only and locked decisions stay locked unless the user reverses them.
- **Attended stages park, they do not poll.** When the next step needs the user (consent screen, credentials, a push only they may run), the lead writes the exact action under `## Blocked on user` in GOAL.md, commits it, says "blocked on user for X" once, and stops **without making any tool call**. Two facts about the built-in `/goal` hook make this the only correct shape: the evaluator clears the goal when the Done-when's blocked clause is satisfied, and the harness ends the loop on its own after a few consecutive turns with no tool use. A lead that polls for the user's action (a `git ls-remote` per turn, a status re-print per turn) is seen as "still working" and gets re-prompted every ~12 seconds until the user returns (freshbooks-tools Phase 6: 465 identical turns, $61, two hours). If a wait must run unattended for hours, start ONE background Bash that waits for the external condition; the goal check then defers on a 30 min / 1 h / 2 h backoff instead of re-prompting. Never fake or skip an attended step; for actions the lead could legitimately do itself (a tag push once the runbook's preconditions hold), ask once whether to self-execute, then do.
- **The model cannot clear a goal.** `/goal clear` is the user's; the blocked clause in Done-when is the lead's only clean exit. Resume is `/goal complete @GOAL.md` again; the lead reads `## Blocked on user`, confirms the action landed, empties the section, and continues.
- To resume after interruption: read `docs/progress.md`, verify `git status --porcelain` and `git log` match its ledger, reconcile before continuing.

## Failure modes to warn the user about

- Phases sized too big stall the Stop-hook loop; prefer two small phases over one heroic one.
- An attended step inside a goal run with no `## Blocked on user` exit is a token loop waiting to happen: the hook re-prompts every few seconds until the user comes back. Every Retarget row flagged "attended" must plan where the lead parks.
- The treadmill is a token black hole by design (independent reviewers, one-tier-up models). The user opted in; do not silently downgrade lanes or models to save tokens -- raise it instead.
- Do not run two phases' gates concurrently in one tree; parallel batches require worktrees and pre-declared shared surfaces.
