# Prompt Refiner Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the prompt-refiner skill as 4 markdown files in `plugins/core/skills/prompt-refiner/`

**Architecture:** Single skill with progressive disclosure via 3 reference files. SKILL.md contains the conversational loop logic. Reference files load on-demand for research strategies, question patterns, and transformation examples.

**Tech Stack:** Markdown (SKILL.md with YAML frontmatter), Claude Code skill architecture

**Design doc:** `docs/plans/2026-03-07-prompt-refiner-design.md`

---

### Task 1: Create directory structure

**Files:**
- Create: `plugins/core/skills/prompt-refiner/`
- Create: `plugins/core/skills/prompt-refiner/references/`

**Step 1: Create the directories**

Run: `mkdir -p plugins/core/skills/prompt-refiner/references`

**Step 2: Verify structure exists**

Run: `ls -la plugins/core/skills/prompt-refiner/`
Expected: Empty directory with `references/` subdirectory

**Step 3: Commit**

```bash
git add plugins/core/skills/prompt-refiner/
git commit -m "feat: scaffold prompt-refiner skill directory"
```

Note: Git won't commit empty dirs. If nothing to commit, proceed to Task 2.

---

### Task 2: Write SKILL.md (core skill logic)

**Files:**
- Create: `plugins/core/skills/prompt-refiner/SKILL.md`
- Reference: `docs/plans/2026-03-07-prompt-refiner-design.md` for approved flow

**Step 1: Write SKILL.md**

The file must contain these sections in order:

**YAML frontmatter:**
```yaml
---
name: prompt-refiner
description: >
  Use when the user asks to refine, improve, restructure, or clarify a prompt
  for Claude Code. Also activates on /refine. Guides users through a conversational
  loop: understands intent, researches the codebase, asks grounded clarifying
  questions, then transforms ramblings into clean structured prompts with
  execute/edit/copy options.
tags:
  function: [engineering, operations, finance, research]
  scenario: [prompt-improvement]
  custom: [prompt-engineering, refine, clarify]
---
```

**Body sections (in order):**

1. **Title and purpose** (2-3 sentences): Transform vague or rambling prompts into clean, structured Claude Code instructions through a conversational loop with deep research.

2. **Invocation** (brief): Explain `/refine <prompt>` or just `/refine`. If no prompt provided, ask what to refine.

3. **Core Process -- Phase 1: Understand Intent**
   - Read the user's raw prompt
   - Categorize: bug fix, feature, refactor, exploration, config/infra, docs
   - If category is obvious from the prompt, skip to Phase 2
   - If unclear, ask 1-2 high-level questions (task type, actual goal)
   - Track loop count (max 3 research-clarify loops)

4. **Core Process -- Phase 2: Deep Research**
   - Load `references/research-strategies.md` for task-scoped checklists
   - Execute research scoped by the task category from Phase 1
   - Budget: 5-8 files/commands per round
   - Check conversation history FIRST before codebase exploration
   - Research tools: Glob, Grep, Read, Bash (git), Explore agent, WebSearch, WebFetch
   - Document findings internally (not shown to user)

5. **Core Process -- Phase 3: Grounded Clarification**
   - Load `references/question-patterns.md` for templates
   - Generate 1-3 questions per round grounded in research findings
   - Use AskUserQuestion with multiple choice where possible
   - Every option must cite specific findings (file paths, function names, patterns found)
   - Adaptive thoroughness: 1 round for simple tasks, 2-3 for complex/risky (auth, data deletion, infra)
   - If research revealed more complexity, loop back to Phase 2 (respect max 3 loops)

6. **Core Process -- Phase 4: Transform**
   - Load `references/transformation-examples.md` for before/after models
   - Show plain-language "Here's what I understood" summary first
   - Wait for user confirmation or correction
   - If corrected, loop back to Phase 3
   - On confirmation, present restructured prompt using this format:
     ```
     ## Goal
     [1-2 sentences]

     ## Context
     [Files, current state, research findings baked in]

     ## Requirements
     - [Extracted from rambling + clarification]

     ## Approach
     [If preference expressed or research suggests one]

     ## Boundaries
     [Only if constraints exist or task is risky]
     ```
   - Sections included only when relevant
   - Present choice: Execute / Edit / Copy

7. **Escape Hatches**
   - "Just do it" or "good enough": transform immediately with current understanding
   - "Start over": reset to Phase 1
   - User can directly edit the understanding summary

8. **Transformation Principles** (concise list)
   - Distill, don't decorate
   - Preserve intent, not wording
   - Surface implicit assumptions
   - Research findings become baked-in context
   - No framework labels

9. **Progressive Disclosure** (link references)
   - Research strategies: `references/research-strategies.md`
   - Question patterns: `references/question-patterns.md`
   - Transformation examples: `references/transformation-examples.md`

**Critical constraints:**
- Target ~200-250 lines total for SKILL.md
- Imperative/infinitive form (avoid "you/your" per severity1 convention)
- Keep it directive -- tell Claude what to do, not what the skill is about
- Follow the existing agent-ops skill conventions (see project-onboard and new-agent skills for style)

**Step 2: Verify SKILL.md parses correctly**

Run: `head -10 plugins/core/skills/prompt-refiner/SKILL.md`
Expected: Valid YAML frontmatter with `---` delimiters, name field, description field, tags

**Step 3: Check line count**

Run: `wc -l plugins/core/skills/prompt-refiner/SKILL.md`
Expected: Between 180 and 280 lines

**Step 4: Commit**

```bash
git add plugins/core/skills/prompt-refiner/SKILL.md
git commit -m "feat: add prompt-refiner core SKILL.md"
```

---

### Task 3: Write references/research-strategies.md

**Files:**
- Create: `plugins/core/skills/prompt-refiner/references/research-strategies.md`
- Reference: `~/projects/claude-prompt-skills/claude-code-prompt-improver/skills/prompt-improver/references/research-strategies.md` for patterns

**Step 1: Write research-strategies.md**

This file is loaded on-demand during Phase 2. It provides task-scoped research checklists.

**Required sections:**

1. **Purpose statement** (1 sentence): Task-scoped research checklists for each prompt category.

2. **Research-first rule**: Always check conversation history before codebase exploration. Never skip research. Never generate questions from assumptions.

3. **Task-scoped checklists** (one per task type, each with 4-6 concrete steps using specific tool names):

   **Bug Fix:**
   - Review conversation history for error messages, stack traces
   - `git log --oneline -10` for recent changes to affected area
   - `Grep` for error patterns, exception types, TODO/FIXME near affected code
   - `Read` the failing code and surrounding context
   - `Glob` for test files covering the affected code
   - Check if error is reproducible from conversation context

   **Feature:**
   - `Explore` agent to map existing architecture patterns
   - `Glob` for similar components (e.g., if adding a new API endpoint, find existing endpoints)
   - `Read` relevant README.md, CLAUDE.md, docs/ for conventions
   - `git log --oneline -20` for recent feature work in the area
   - Check package.json/requirements.txt for available libraries

   **Refactor:**
   - `Grep` for all imports/usages of the target (map dependencies)
   - `Read` the target code and its test file
   - `git log --oneline path/to/file` for change frequency (hot files = higher risk)
   - `Glob` for similar patterns elsewhere (is this a one-off or systemic?)
   - Check test coverage: `Glob` for `*test*` or `*spec*` files matching the target

   **Exploration:**
   - `Explore` agent with "very thorough" for broad codebase scan
   - `Read` CLAUDE.md, README.md at project root and key subdirectories
   - `Bash`: `ls` top-level directory structure
   - `Read` package.json / pyproject.toml / Cargo.toml for tech stack
   - Check for docs/ directory and architectural documentation

   **Config/Infra:**
   - `Glob` for config files: `**/*config*.{json,yaml,yml,toml}`, `**/.env*`
   - `Read` existing config files to understand current setup
   - `git log --grep="config" --oneline -10` for config change history
   - Check for deployment docs, CI/CD files, Dockerfiles
   - `Grep` for environment variable references: `process.env`, `os.environ`, `env::`

   **Docs:**
   - `Read` the code being documented
   - `Glob` for existing docs to match style: `**/*.md`, `**/docs/**`
   - `Read` CLAUDE.md for documentation conventions
   - Check for doc generation tools (JSDoc, Sphinx, rustdoc configs)

4. **Research budget**: 5-8 files/commands per round. If the task needs more, the conversational loop naturally provides another round after clarification narrows the scope.

5. **Research output format** (internal, not shown to user):
   ```
   Findings:
   - [File/source]: [What was found]
   - [File/source]: [What was found]
   Patterns: [Existing patterns relevant to the task]
   Gaps: [What's still unclear -- drives questions in Phase 3]
   ```

**Target:** ~120-160 lines

**Step 2: Verify file exists and is reasonable length**

Run: `wc -l plugins/core/skills/prompt-refiner/references/research-strategies.md`
Expected: Between 100 and 180 lines

**Step 3: Commit**

```bash
git add plugins/core/skills/prompt-refiner/references/research-strategies.md
git commit -m "feat: add prompt-refiner research strategies reference"
```

---

### Task 4: Write references/question-patterns.md

**Files:**
- Create: `plugins/core/skills/prompt-refiner/references/question-patterns.md`
- Reference: `~/projects/claude-prompt-skills/claude-code-prompt-improver/skills/prompt-improver/references/question-patterns.md` for patterns

**Step 1: Write question-patterns.md**

This file is loaded on-demand during Phase 3. It provides grounded question templates.

**Required sections:**

1. **Core rules** (brief):
   - Every option must come from research findings
   - 1 decision point per question
   - 2-4 options per question
   - Include trade-offs in descriptions
   - User can always provide freeform input

2. **AskUserQuestion format** (compact reference):
   ```
   question: ends with ?
   header: max 12 chars
   multiSelect: true/false (always specify)
   options: 2-4 items, each with label (1-5 words) and description (trade-offs)
   ```

3. **Question templates by category** (each with one concrete example showing research-grounded options):

   **Target** -- "Which file/component?" when research found multiple candidates
   **Scope** -- "Should this also affect X?" when research revealed related code
   **Approach** -- "I found pattern A here and pattern B there, which should this follow?"
   **Risk** -- "This touches [sensitive area]. Should I [conservative] or [aggressive]?"
   **Acceptance** -- "How will you know this is done?" for vague success criteria

4. **Adaptive thoroughness guide**:
   - Simple (1 round): target is clear, approach has one obvious path
   - Moderate (2 rounds): multiple valid approaches, or scope is ambiguous
   - Complex (3 rounds): touches auth/data/infra, or multiple interconnected decisions

5. **Anti-patterns** (brief, 3-4 items):
   - Generic options not grounded in research
   - Compound questions (2 decisions in 1 question)
   - More than 4 options (split into multiple questions)
   - Leading questions that bias toward one answer

**Target:** ~100-140 lines. Lean and practical -- templates, not essays. Borrow the best patterns from severity1's question-patterns.md but keep it half the length.

**Step 2: Verify file**

Run: `wc -l plugins/core/skills/prompt-refiner/references/question-patterns.md`
Expected: Between 80 and 160 lines

**Step 3: Commit**

```bash
git add plugins/core/skills/prompt-refiner/references/question-patterns.md
git commit -m "feat: add prompt-refiner question patterns reference"
```

---

### Task 5: Write references/transformation-examples.md

**Files:**
- Create: `plugins/core/skills/prompt-refiner/references/transformation-examples.md`

**Step 1: Write transformation-examples.md**

This file is loaded on-demand during Phase 4. It provides before/after examples for each task type.

**Required sections:**

1. **Purpose** (1 sentence): Before/after transformation examples showing how ramblings become structured prompts.

2. **Examples** (one per major task type, each showing):
   - The raw rambling input
   - The "Here's what I understood" summary
   - The structured output prompt (using Goal/Context/Requirements/Approach/Boundaries format)

   **Bug Fix Example:**
   - Raw: "the login is broken again, something about tokens idk, users keep getting kicked out, it was fine yesterday"
   - Understood: "Fix the JWT validation failure in `src/auth/login.ts` that started after yesterday's commit `a3f2b1c`. Users are getting 401 errors and being logged out mid-session. The token refresh flow in `src/auth/refresh.ts` should remain untouched."
   - Structured: Goal + Context (specific files, commit) + Requirements (fix validation, preserve refresh flow) + Boundaries (don't touch OAuth)

   **Feature Example:**
   - Raw: "we need some kind of caching, the dashboard is slow, maybe redis? or whatever, just make it faster"
   - Understood: "Add Redis caching to the dashboard API endpoints in `src/api/dashboard.ts`. The `/api/dashboard/stats` endpoint currently makes 4 database queries averaging 800ms total. Cache responses with a 5-minute TTL, using the existing Redis connection in `src/db/redis.ts`."
   - Structured: Goal + Context (endpoints, current perf, existing Redis) + Requirements (TTL, specific endpoints) + Approach (Redis, matching existing patterns)

   **Refactor Example:**
   - Raw: "the user service is a mess, like 500 lines, functions everywhere, can you clean it up somehow"
   - Understood: "Split `src/services/UserService.ts` (487 lines, 12 methods) into focused modules. The validation methods (`validateEmail`, `validatePassword`, `validateProfile`) should move to `UserValidationService`. The notification methods (`sendWelcomeEmail`, `sendPasswordReset`) should move to `UserNotificationService`. Keep the core CRUD methods in `UserService`."
   - Structured: Goal + Context (current size, method inventory) + Requirements (specific split strategy) + Boundaries (preserve existing tests, keep public API compatible)

3. **Transformation principles reminder** (brief, 3-4 bullets):
   - Research findings become specific file paths, function names, line numbers in the output
   - Shorter is better -- strip filler, hedge language, tangents
   - Only include sections that add information (skip empty Approach or Boundaries)
   - The "understood" summary is conversational; the structured prompt is directive

**Target:** ~100-130 lines. Concrete examples, minimal commentary.

**Step 2: Verify file**

Run: `wc -l plugins/core/skills/prompt-refiner/references/transformation-examples.md`
Expected: Between 80 and 150 lines

**Step 3: Commit**

```bash
git add plugins/core/skills/prompt-refiner/references/transformation-examples.md
git commit -m "feat: add prompt-refiner transformation examples reference"
```

---

### Task 6: Validate skill structure

**Files:**
- Verify: `plugins/core/skills/prompt-refiner/SKILL.md`
- Verify: `plugins/core/skills/prompt-refiner/references/research-strategies.md`
- Verify: `plugins/core/skills/prompt-refiner/references/question-patterns.md`
- Verify: `plugins/core/skills/prompt-refiner/references/transformation-examples.md`

**Step 1: Verify all files exist**

Run: `find plugins/core/skills/prompt-refiner/ -type f | sort`
Expected:
```
plugins/core/skills/prompt-refiner/SKILL.md
plugins/core/skills/prompt-refiner/references/question-patterns.md
plugins/core/skills/prompt-refiner/references/research-strategies.md
plugins/core/skills/prompt-refiner/references/transformation-examples.md
```

**Step 2: Verify YAML frontmatter parses**

Run: `head -20 plugins/core/skills/prompt-refiner/SKILL.md`
Expected: Valid frontmatter with name: prompt-refiner, description, and tags

**Step 3: Verify all reference links in SKILL.md point to existing files**

Run: `grep -o 'references/[a-z-]*\.md' plugins/core/skills/prompt-refiner/SKILL.md | sort -u`
Expected: All 3 reference files listed

**Step 4: Check total token budget**

Run: `wc -l plugins/core/skills/prompt-refiner/SKILL.md plugins/core/skills/prompt-refiner/references/*.md`
Expected: SKILL.md ~200-250 lines, each reference ~100-160 lines, total ~500-700 lines

**Step 5: Verify UTF-8 encoding (agent-ops convention)**

Run: `file plugins/core/skills/prompt-refiner/SKILL.md plugins/core/skills/prompt-refiner/references/*.md`
Expected: All files show "UTF-8 Unicode text" or "ASCII text"

---

### Task 7: Update registry and commit

**Files:**
- Modify: `registry.yaml` (if it lists skills)
- No other files

**Step 1: Check if registry.yaml needs updating**

Run: `cat registry.yaml`
Determine if skills are listed and if prompt-refiner needs to be added.

**Step 2: Update registry if needed**

Add prompt-refiner entry following the existing format.

**Step 3: Final commit**

```bash
git add -A plugins/core/skills/prompt-refiner/ registry.yaml
git commit -m "feat: complete prompt-refiner skill with references"
```

**Step 4: Push**

```bash
git push
```
