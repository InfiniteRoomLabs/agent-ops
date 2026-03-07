---
name: prompt-refiner
description: >
  Use when the user asks to refine, improve, restructure, or clarify a prompt
  for Claude Code. Also activates on /refine. Guides through a conversational
  loop: understands intent, researches the codebase, asks grounded clarifying
  questions, then transforms ramblings into clean structured prompts with
  execute/edit/copy options.
tags:
  function: [engineering, operations, finance, research]
  scenario: [prompt-improvement]
  custom: [prompt-engineering, refine, clarify]
---

# Prompt Refiner

Transform vague or rambling prompts into clean, structured Claude Code instructions through a conversational loop with deep research. Invoked via `/refine <prompt>` or `/refine` (then ask what to refine).

## Escape Hatches

Recognize these at any point in the flow:

- **"Just do it"** or **"good enough"**: Transform immediately with current understanding, skip remaining questions
- **"Start over"**: Reset to Phase 1
- User directly edits the understanding summary: Accept edits as corrections

## Phase 1: Understand Intent

Read the raw prompt. Categorize:

| Category | Signals |
|----------|---------|
| Bug fix | "broken", "error", "fix", "crash", "failing", stack traces |
| Feature | "add", "create", "implement", "new", "build" |
| Refactor | "clean up", "reorganize", "split", "extract", "simplify" |
| Exploration | "how does", "understand", "explain", "what is" |
| Config/Infra | "deploy", "config", "environment", "CI", "docker" |
| Docs | "document", "README", "explain for others", "write docs" |

**If category is obvious from the prompt**: Skip to Phase 2.

**If unclear**: Ask 1-2 high-level questions about task type and actual goal. Use `AskUserQuestion` with multiple choice.

### Compound Detection

After categorization, check: does the prompt contain 3+ distinct concerns, reference multiple projects, or mix definite decisions with exploratory ideas? If so, treat it as a **compound prompt**:

1. Identify each concern cluster and its certainty level (decided, exploring, just an example)
2. Note which projects/repos are referenced
3. Proceed to Phase 2 with cross-cutting research rather than a single-category checklist
4. In Phase 3, prioritize decomposition questions before diving into any single cluster

Track loop count. Maximum 3 research-clarify loops total across Phases 2-3.

## Phase 2: Deep Research

Load `references/research-strategies.md` for task-scoped checklists.

Execute research scoped by the category from Phase 1:

1. **Check conversation history first** -- recent messages, error output, file views
2. Run the task-scoped research checklist (bug fix, feature, refactor, etc.)
3. Budget: 5-8 files/commands per round

Available research tools:
- `Glob` -- find files by pattern
- `Grep` -- search file contents
- `Read` -- read specific files
- `Bash` -- git log, git blame, directory listings
- `Agent` with `subagent_type=Explore` -- broad codebase exploration
- `WebSearch` / `WebFetch` -- external docs, best practices

Document findings internally using this format (not shown to user):

```
Findings:
- [File/source]: [What was found]
- [File/source]: [What was found]
Patterns: [Existing patterns relevant to the task]
Gaps: [What's still unclear -- drives questions in Phase 3]
```

## Phase 3: Grounded Clarification

Load `references/question-patterns.md` for templates.

Generate 1-3 questions per round. Every question must cite specific research findings.

### Question Rules

- Use `AskUserQuestion` with multiple choice where possible
- Every option must reference specific findings (file paths, function names, patterns)
- 1 decision point per question
- 2-4 options per question
- Include trade-offs in option descriptions
- User can always provide freeform input

### Adaptive Thoroughness

| Complexity | Rounds | Signals |
|------------|--------|---------|
| Simple | 1 | Target is clear, one obvious approach |
| Moderate | 2 | Multiple valid approaches, ambiguous scope |
| Complex | 3 | Touches auth/data/infra, multiple interconnected decisions |

### Loop Control

After each clarification round, assess:
- **Sufficient understanding?** Proceed to Phase 4
- **Research revealed more complexity?** Loop back to Phase 2 (respect max 3 loops)
- **User said "just do it"?** Proceed to Phase 4 with current understanding

## Phase 4: Transform

Load `references/transformation-examples.md` for before/after models.

### Step 1: Show Understanding

Present a plain-language summary:

> **Here's what I understood:**
>
> [2-4 sentences describing the task, target, approach, and any constraints -- in conversational tone]

Wait for user response:
- **Confirms**: Proceed to Step 2
- **Corrects**: Incorporate corrections, loop back to Phase 3 if needed
- **Edits directly**: Accept edits as the new understanding

### Step 2: Present Structured Prompt

Transform into this format (include sections only when relevant):

```
## Goal
[1-2 sentences: what to accomplish]

## Context
[Files involved, current state, constraints from research]

## Requirements
- [Specific requirements extracted from the rambling + clarification]

## Approach
[If preference expressed or research suggests one]

## Boundaries
[What NOT to do -- only if constraints exist or task is risky]
```

### Compound Output Format

When transforming a compound prompt, use this alternative structure:

```
## Goal
[Overarching objective -- 1-2 sentences]

## Work Streams

### 1. [Stream name]
**Goal**: [What this stream accomplishes]
**Context**: [Relevant findings]
**Requirements**: [Specifics]
**Open questions**: [Things still uncertain]

### 2. [Stream name]
...

## Sequencing
[Which streams depend on others, suggested order]

## Boundaries
[Cross-cutting constraints]
```

### Step 3: User Choice

Present three options:

1. **Execute** -- Run the refined prompt directly in this conversation (do NOT re-invoke prompt-refiner)
2. **Edit** -- User modifies the prompt, then execute
3. **Copy** -- Place the prompt on clipboard, done

### Skill Chaining

When the raw prompt contains phrases like "let's brainstorm," "let's plan," "generate a plan," or references a specific workflow, recognize these as implicit skill invocations. Adjust the Execute option:

- "Let's brainstorm" -> Execute feeds the refined prompt into the brainstorming skill
- "Generate a plan" -> Execute feeds into spec-kitty.plan or writing-plans
- No skill reference -> Execute runs the refined prompt directly in conversation

Note the target skill in the Execute option so the user knows what will happen.

## Transformation Principles

- Distill, don't decorate -- shorter and clearer beats longer
- Preserve intent, not wording
- Surface implicit assumptions the user didn't state
- Research findings become baked-in context (file paths, function names, error messages)
- No framework labels (CO-STAR, RISEN, etc.) -- just clean, direct instructions
- Only include sections that add information -- skip empty ones

## Progressive Disclosure

These references load on-demand during specific phases:

- **Research strategies**: `references/research-strategies.md` -- task-scoped checklists (Phase 2)
- **Question patterns**: `references/question-patterns.md` -- grounded question templates (Phase 3)
- **Transformation examples**: `references/transformation-examples.md` -- before/after models (Phase 4)
