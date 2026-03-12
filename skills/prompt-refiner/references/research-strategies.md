# Research Strategies

Task-scoped research checklists for Phase 2 of the prompt refiner.

## Research-First Rule

1. Check conversation history before codebase exploration -- errors, file views, recent decisions
2. Never skip research. Never generate questions from assumptions
3. Ground every Phase 3 question in specific findings from this phase

## Task-Scoped Checklists

Each checklist targets 5-8 files/commands per round. Pick the checklist matching the task category from Phase 1.

### Bug Fix

1. Review conversation history for error messages, stack traces, reproduction steps
2. `git log --oneline -10` for recent changes to the affected area
3. `Grep` for error patterns, exception types, TODO/FIXME near affected code
4. `Read` the failing code path and surrounding context
5. `Glob` for test files covering the affected code (`*test*`, `*spec*`)
6. Check if the error is reproducible from conversation context alone

### Feature

1. `Agent` (Explore) to map existing architecture patterns in the relevant area
2. `Glob` for similar components (if adding an endpoint, find existing endpoints)
3. `Read` relevant README.md, CLAUDE.md, docs/ for conventions and constraints
4. `git log --oneline -20` for recent feature work in the same area
5. Check package.json / pyproject.toml / Cargo.toml for available libraries
6. `Grep` for imports or patterns the new feature should follow

### Refactor

1. `Grep` for all imports/usages of the target -- map the dependency graph
2. `Read` the target code and its test file(s)
3. `git log --oneline <path>` for change frequency (hot files = higher risk)
4. `Glob` for similar patterns elsewhere -- is this a one-off or systemic?
5. Check test coverage: `Glob` for `*test*` or `*spec*` files matching the target
6. Identify coupling points that could break during extraction

### Exploration

1. `Agent` (Explore, "very thorough") for broad codebase scan
2. `Read` CLAUDE.md and README.md at project root and key subdirectories
3. `Bash`: `ls` top-level directory structure
4. `Read` package.json / pyproject.toml / Cargo.toml for tech stack
5. Check for docs/ directory and architectural documentation
6. `git log --oneline -20` for a sense of recent development activity

### Config/Infra

1. `Glob` for config files: `**/*config*.{json,yaml,yml,toml}`, `**/.env*`
2. `Read` existing config files to understand current setup
3. `git log --grep="config" --oneline -10` for config change history
4. Check for deployment docs, CI/CD files (`.github/workflows/`, `Dockerfile`)
5. `Grep` for environment variable references (`process.env`, `os.environ`, `env::`)
6. `Read` any infrastructure-as-code files (Terraform, Ansible, etc.)

### Docs

1. `Read` the code being documented
2. `Glob` for existing docs to match style: `**/*.md`, `**/docs/**`
3. `Read` CLAUDE.md for documentation conventions
4. Check for doc generation tools (JSDoc configs, Sphinx conf.py, rustdoc)
5. `Grep` for existing doc patterns (comment style, section headings)

### Compound / Multi-Project

Use when the prompt references multiple repos, contains 3+ distinct concerns, or spans exploration + planning.

1. Identify all projects/repos referenced in the prompt
2. `Read` CLAUDE.md in each referenced project for structure, conventions, and existing decisions
3. If "ideas" repo referenced: `Glob` for relevant idea files (`ideas/*.md`), `Read` them
4. Map which concerns belong to which project/repo
5. For each concern cluster, run 2-3 targeted research commands (use the matching single-category checklist above)
6. Check for existing infra/config that relates to the concerns (`Glob` for Terraform, Docker, CI configs)
7. `git log` across referenced repos for recent related work
8. Note certainty levels: which decisions are made vs. which are exploratory

Research budget scales: allow 5-8 commands **per concern cluster** rather than per round, since compound prompts cover more ground.

## Research Budget

- **Per round**: 5-8 files/commands
- **If more is needed**: The conversational loop naturally provides another round after clarification narrows the scope
- **Don't over-research**: Stop when you have enough findings to ask grounded questions

## Research Output Format

Document findings internally (not shown to user):

```
Findings:
- [File/source]: [What was found]
- [File/source]: [What was found]
Patterns: [Existing patterns relevant to the task]
Gaps: [What's still unclear -- drives questions in Phase 3]
```

Findings surface as:
- Grounded question options in Phase 3 (citing specific files, functions, patterns)
- Baked-in context in the final structured prompt (Phase 4)
