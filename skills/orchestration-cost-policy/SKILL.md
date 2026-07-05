---
name: orchestration-cost-policy
description: "Use when deciding HOW to execute non-trivial work: which orchestration mechanism (inline, subagent fan-out, workflow) and which model tier per task. Applies before dispatching agents, spawning workflows, or doing large work in the main loop. The rule: maximize results per token, weighting model effectiveness against cost for the specific task."
tags:
  function: [engineering, operations, executive]
  scenario: [multi-agent-orchestration, model-selection, task-dispatch]
  custom: [cost-efficiency, token-budget]
---

# Orchestration Cost Policy

One rule, globally: **pick the mechanism and model tier that produce the best results for the fewest tokens, evaluated per task as (model effectiveness for this task) vs (token cost).** No loyalty to any tool. This is a standing directive from Wes -- he works against a 5-hour usage window, so orchestration overhead directly costs working time.

## Model tier selection

| Task shape | Tier |
|---|---|
| Judgment-heavy: contract/API semantics, state machines, architecture, gnarly merges, security-sensitive code, establishing a pattern others copy | Opus (or the session's top model) |
| Pattern-following: CRUD against an established exemplar, porting per a written work order, test scaffolding, docs, mechanical refactors | Sonnet |
| Pure-mechanical sweeps: renames, inventory/grep summarization, format fixes at scale | Haiku |

When unsure between two tiers, ask: "would the cheaper model's failure be caught by an existing gate (tests, lint, drift check)?" If yes, go cheaper -- the gate converts quality risk into a cheap retry.

## Mechanism selection

- **Inline (main loop)**: small known edits, adjudication, merges requiring judgment. Never burn main-loop context on bulk file reading a subagent could summarize.
- **Subagent fan-out (Agent tool)**: iteration count known and small; each unit independently verifiable; parallelize only when writers touch disjoint files (or use worktrees + planned merges).
- **Workflow**: unknown-size work discovered as you go (loop-until-dry), or when deterministic control flow over many stages saves repeated main-loop reasoning. Do not use it to automate a loop whose expensive step is human/orchestrator judgment -- the script only automates the cheap part.

## Token hygiene (all mechanisms)

- Brief agents with pointers to files + a written work order, not pasted bulk content -- unless the content is small and saves the agent a discovery pass.
- Do not re-read or re-verify what a subagent already verified under a gate; spot-check the gate instead.
- Batch verification into single commands; batch independent tool calls into one message.
- Prefer existing gates (tests, lint, CI checks, drift ledgers) over reviewer agents for mechanical correctness; spend reviewer agents on semantics only.

## Escalation

If best-results and cheapest genuinely conflict (quality bar not reachable at the affordable tier), surface the tradeoff to the user with a recommendation instead of silently picking either.
