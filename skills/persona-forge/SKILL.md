---
name: persona-forge
description: Use when a task would benefit from a purpose-built persona instead of a generic assistant voice -- analysis, review, writing, architecture, negotiation, teaching, debugging, any role-shaped work. Generates several candidate personas for the role, antagonistically attacks each for bias and blind spots, evolves the survivors through at least two merge-attack-refine rounds into one optimal persona spec, then adopts that persona for the work phase.
tags:
  function: [research, executive, engineering, operations]
  scenario: [decision-support, design-review, strategy-review, content-creation, role-assignment]
  custom: [persona, red-team, adversarial, role-play, bias-control, meta-prompting]
---

# Persona Forge

Forge the right worker before working. Instead of doing role-shaped work as a generic assistant, generate competing personas for the role, stress-test them against each other, and adopt the one that survives.

## Why

Output quality is bounded by the lens producing it. A growth-hacker persona tells a calm-company founder to build funnels he rejects. A pure idealist never prices risk. A senior-architect persona reviews a prototype like it's a bank core. The wrong persona fails silently -- the output looks competent but optimizes for the wrong things. Forging the persona first, and attacking it, surfaces the worker's biases BEFORE they contaminate the work, and declares the residue openly so the consumer can discount it.

The pattern is task-agnostic. Any work that has a "who should do this?" answer better than "an assistant" qualifies: viability verdicts, code/design review, technical writing for a specific audience, API design, incident post-mortems, pricing strategy, curriculum design, negotiation prep.

## When to Use

- The task is judgment-heavy and the "house view" risks flattery, genericness, or wrong-altitude review
- The user has a "challenge, don't flatter" expectation
- Multiple stakeholder lenses conflict (operator vs. buyer vs. builder vs. ethicist) and one coherent voice must carry the work
- The same role will recur (the forged spec is reusable)

Do NOT use for: factual lookups, syntax help, tasks with one canonical answer, mechanical edits, or quick checks. Forge cost is ~1 extra agent run; spend it only when the work's quality hinges on perspective.

## Process

Delegate Phases 1-3 to a single subagent (general-purpose) so the forge happens in isolated context; the parent adopts the result in Phase 4. Pass the subagent:

- The task the persona will perform
- All relevant context (domain facts, constraints, audience, what the requester values, what options are on the table)
- Any standing rules the persona must respect (e.g. "challenge, don't flatter")

### Phase 1 -- Candidate Generation

Generate 3-5 genuinely different candidate personas for the role. Each candidate gets:

- **Name** and one-line archetype
- **Background scars**: specific failures/wins that shaped their heuristics (scars, not resumes -- "lost $400k to churn he priced wrong" beats "20 years experience")
- **Core operating heuristics**: what they always do/ask first in this role
- **What they uniquely catch or produce** that other lenses miss
- **Voice**: how they talk

Force diversity along the axes that matter for THIS task: operator vs. buyer vs. builder; optimist vs. cynic; inside-the-domain vs. outside; values-aligned vs. values-hostile; practitioner vs. theorist. At least one candidate should be uncomfortable for the requester.

### Phase 2 -- Antagonistic Evolution

For EACH candidate, attack it as sole performer of THIS task:

- What does this persona systematically miss or get wrong?
- Where is it unfairly harsh, unfairly soft, or mis-calibrated for this specific task/requester combination?
- What bias disqualifies it from being the only voice?

Be concrete. "The growth person optimizes for funnels the founder explicitly rejects -- output collapses to 'do the thing you refuse to do', useless."

Then evolve through AT LEAST two rounds:

1. **Round 1 merge**: combine surviving traits from the attacked candidates into a composite; kill disqualified traits explicitly (say what died and why)
2. **Attack the merge**: the composite has new failure modes (often: bland average, contradictory heuristics, scar soup). Find them.
3. **Round 2 refinement**: resolve the contradictions; sharpen back to a coherent single character. A persona that believes everything believes nothing.

### Phase 3 -- Final Persona Spec

The deliverable. Must contain ALL of:

- **Name** + one-paragraph biography with specific scars
- **6-10 numbered operating heuristics** ("I always...")
- **Declared retained biases** -- kept on purpose, stated so the consumer can discount them
- **Named blind spots** -- what this persona STILL cannot see; honesty here is the quality bar
- **Voice/tone instructions**
- **Opening moves**: the first 3-5 questions it would ask or steps it would take on the task

### Phase 4 -- Adoption

The parent agent adopts the spec verbatim for the work phase:

1. Announce the persona to the user in 2-3 lines (name, scars, declared biases) so they know whose voice they are reading
2. Do the work IN CHARACTER, with the numbered heuristics visibly driving the structure
3. Close by stepping out of character for one short paragraph: note where the persona's declared biases or blind spots most likely skewed the output

## Output Contract

Two artifacts:

1. The persona spec (from Phase 3) -- keep it; it is reusable for follow-up work in the same role. For recurring roles, consider promoting a proven spec to a permanent agent definition in `agents/{division}/`.
2. The in-character work product with the out-of-character bias footnote

## Anti-Patterns

- **Persona as costume**: adopting the name but working generically. The heuristics must visibly drive the structure of the output.
- **Flattery laundering**: forging a persona predisposed to like the requester's plan. Phase 2 exists to kill this; if every candidate agrees with the requester, generate a hostile one and run the attack again.
- **Scar inflation**: vague credentials instead of specific formative failures. Scars create heuristics; resumes create authority cosplay.
- **Skipping the second attack round**: the round-1 merge is almost always an incoherent average. The product is forged in round 2.
- **Forging for forging's sake**: if "an assistant" is genuinely the right worker (mechanical task, single canonical answer), skip the skill.
