# Changelog

All notable changes to the agent-ops marketplace will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [agency-1.13.1] - 2026-05-20

### Fixed
- **`scripts/commit_guard.py`** -- `build/` no longer trips a false positive on non-Java repos. The pattern now requires evidence of a Gradle/Maven project (`build.gradle`, `pom.xml`, `gradlew`, `mvnw`, etc., at root or in any module) before flagging. Reasoning: `build/` is Gradle's canonical output dir, but many repos use `build/` for shell scripts, Docker build contexts, or CI helpers (e.g. amborle/featmap's `build/build_webapp.sh`) -- the basename alone is ambiguous. Mirrors the same predicate pattern already used for `packages/` (.NET vs. JS workspace).

### Added
- **`docs/superpowers/`** -- captures the plan and design spec behind the commit-guard predicate fix (`plans/2026-03-26-commit-guard.md`, `specs/2026-03-26-commit-guard-design.md`) so future passes have the reasoning, not just the diff.

## [agency-1.13.0] - 2026-05-18

### Added
- **Cross-agent coordination tools** added to all 155 agent frontmatters. Tier 1 (every agent): `SendMessage`, `TaskCreate`, `TaskGet`, `TaskUpdate`, `TaskList`, `TaskOutput` -- so any specialist can address peers by name and read/write the shared task board. Tier 2 (14 leads/orchestrators: CEO, Orchestrator, Reality Checker, CTO, VP Eng, DevOps Manager, Security Lead, Incident Commander, Studio Producer/Operations, Project Shepherd, QA Triage Lead, Test Strategist, Sprint Prioritizer): additionally `TeamCreate`, `TeamDelete`, `TaskStop` -- team-spawn and task-kill authority that maps to org-chart seniority. Converts the agency from a parent-only spawn tree into a peer-to-peer graph with a shared work board.
- **`tools/add_coordination_tools.py`** -- idempotent bulk-edit script that classifies agents by relative path, preserves original tools-list format (bracketed vs comma), and skips any agent already holding the full additive set. Safe to re-run as new agents land.

## [agency-1.12.2] - 2026-05-01

### Changed
- **CLAUDE.md** documents the release workflow: which files carry which version, when each bump level applies, and that `tools/version_bump.py` is the canonical way to update them. Future agents/sessions should use the script, not hand-edit, so plugin.json and pyproject.toml stay in sync and `uv.lock` gets refreshed.

## [agency-1.12.1] - 2026-05-01

### Added
- **`tools/version_bump.py`** -- repo-internal version bumper that updates `pyproject.toml`, `.claude-plugin/plugin.json`, and the agency entry in `.claude-plugin/marketplace.json` independently, with `--plugin`, `--pyproject`, `--marketplace`, and `--all` flags accepting `major|minor|patch` or `set:X.Y.Z`. Refreshes `uv.lock` automatically when `pyproject.toml` is touched. Warns when plugin and pyproject would diverge (the version-guard hook would block the resulting commit). Lives under `tools/` to flag it as not part of any plugin distribution surface.
- **`tests/test_version_bump.py`** -- 16 tests covering bump-level parsing, `set:X.Y.Z` overrides, file round-trips, and the typer-driven end-to-end paths (all/plugin-only/marketplace-only/dry-run/no-args).

## [agency-1.12.0] - 2026-05-01

### Added
- **`render-mermaid` skill** (`skills/render-mermaid/`) -- renders a mermaid diagram (from a `.mmd` file or piped stdin) and opens it in the user's default viewer. Defaults tuned for Linux + sandboxed browsers: PDF output (vector + baked fonts so text survives mermaid's CSS-variable rendering quirks in `eog`/Loupe and system dark mode), output written to `~/Downloads/` so snap/flatpak Firefox can read it, Puppeteer launched with `--no-sandbox` so Ubuntu 23.10+ AppArmor doesn't block Chromium. Description scoped tightly: triggers on "render/visualize/view/open/show me as a diagram" only -- not on plain mermaid authoring -- so it doesn't burn tokens when the user is just writing or editing mermaid source.
- **`scripts/templates/`** convention extended: skill-local helpers may now ship as siblings of `SKILL.md` (e.g. `skills/render-mermaid/render_mermaid.py`) rather than under `scripts/`. Inline PEP 723 dependency headers keep them runnable via `uv run`.

## [agency-1.11.1] - 2026-05-01

### Changed
- **CHANGELOG header** now matches the canonical Keep a Changelog 1.1.0 + Semantic Versioning 2.0.0 two-paragraph block emitted by `scripts/templates/CHANGELOG.template.md`. Project-specific phrasing ("agent-ops marketplace") preserved.

## [agency-1.11.0] - 2026-05-01

### Added
- **CHANGELOG bootstrap in `scripts/changelog-guard.py`** -- when committing on a protected branch with no `CHANGELOG.md` present, the guard now writes an example template to the repo root before blocking. The block message instructs the agent to keep the canonical 5-line header (title + Keep a Changelog + Semantic Versioning paragraphs), delete the example block, and replace it with real release entries.
- **`scripts/templates/CHANGELOG.template.md`** -- standalone artifact owning the template body. Single `{{DATE}}` placeholder; demonstrates all six Keep a Changelog section names (Added, Changed, Deprecated, Removed, Fixed, Security) across two example patch releases of a fictional `widget` CLI, plus an HTML comment describing what to keep and what to replace.
- **`tests/test_changelog_guard.py`** -- 10 tests covering template rendering, `{{DATE}}` substitution, file generation, and every branch of `evaluate()` including the no-overwrite guarantee when an existing CHANGELOG is present but unstaged.

## [agency-1.10.2] - 2026-05-01

### Added
- **Python dev environment** (`pyproject.toml`, `pyrightconfig.json`, `.zed/settings.json`) -- declares dev-only dependency manifest (`pydantic`, `typer`, `semver`, `pyyaml`, `pytest`) so editor LSPs (basedpyright/pyright) resolve imports for `scripts/` and `tests/`. Runtime scripts still use PEP 723 inline dependency headers and run via `uv run`. `pyrightconfig.json` pins venv path; `.zed/settings.json` forces basedpyright with `extraPaths=["scripts"]`.
- `.venv/` to `.gitignore`.

### Fixed
- **Builtin shadowing in `scripts/summon.py`** -- the Typer command `def list(...)` shadowed `builtins.list` at module scope, causing every `list[X]` annotation in the file to resolve to the function rather than the type. Renamed to `def list_agents` with `@app.command(name="list")` so the CLI surface is unchanged. Removed unused `import hashlib`.

## [agency-1.10.1] - 2026-04-30

### Changed
- **Marketplace entry** (`.claude-plugin/marketplace.json`) -- bumped agency plugin entry from 1.2.0 to 1.2.1 so the marketplace catalog reflects the commit-guard hotfix.

### Fixed
- **commit-guard `packages/` false positive** (`scripts/commit_guard.py`) -- the `.NET: packages/` rule was blocking commits in pnpm/npm/yarn/lerna/nx/turborepo workspaces where `packages/` is the standard source root. Heuristic now requires real .NET evidence (`.csproj`/`.sln`/`global.json`/`NuGet.Config`/legacy `<packages>` element in a csproj) before flagging, and skips entirely when JS workspace evidence is detected. Other .NET artifact dirs (`bin/`, `obj/`) remain unconditionally blocked. Reproduction case: `claudesync` repo at `~/projects/infinite-room-labs/claudesync` could no longer commit `packages/core/src/sync/state.ts`.

### Added
- **commit-guard regression tests** (`tests/test_commit_guard.py`) -- 18 tests covering pnpm/npm-workspaces/lerna/nx/turbo allowlists, modern + legacy `<packages>` .NET repos, unconditional `bin/`/`obj/` blocking, and detector unit coverage.
- **`requires` predicate field on `IgnoredPattern`** -- per-pattern context gate, evaluated once per repo and cached. Future ambiguous patterns can opt in without touching `find_violations`.

## [agency-1.10.0] - 2026-04-02

### Added
- **ADHD Accessibility output style** (`output-styles/adhd.md`) -- first-class output style replacing the old skill-based approach. All 9 behavioral rules (micro-chunking, reduced decisions, response brevity, momentum preservation, progress dopamine, context anchoring, anti-rabbit-hole guardrails, time awareness, sensory-friendly formatting) baked in with recommended defaults. Activate via `/config` -> Output style -> ADHD Accessibility.
- **Output styles support** in `plugin.json` -- `outputStyles` field pointing to `./output-styles/` directory

### Removed
- `skills/accessibility-adhd/SKILL.md` -- replaced by the ADHD output style
- `commands/init-adhd.md` -- no longer needed; output styles are selected via `/config`
- `scripts/accessibility-config.py` -- SessionStart hook detection no longer needed
- `accessibility-config.py` entry from SessionStart hooks in `hooks.json`
- `accessibility-adhd` and `init-adhd` entries from `registry.yaml`

### Changed
- `docs/guides/accessibility-adhd.md` rewritten to document the output style approach with migration instructions from the old skill-based system

## [agency-1.9.0] - 2026-03-26

### Added
- **7 new agents** closing coverage gaps across the software-house lifecycle:
  - `integration-engineer` (engineering) -- third-party SaaS integrations (Stripe, OAuth, S3, etc.)
  - `requirements-engineer` (product) -- structured requirements elicitation, PRDs, user story maps
  - `lead-finder` (research) -- ICP matching, prospect scoring, pipeline entry point
  - `debugger` (engineering) -- hypothesis-driven bug investigation with IRL stack awareness
  - `retro-facilitator` (project-management) -- sprint retros, kaizen metrics, action item tracking
  - `test-strategist` (testing) -- test pyramid selection, risk-based coverage targets
  - `qa-triage-lead` (testing, haiku) -- defect lifecycle, severity classification, routing
- **4 NEXUS quality gates**: scoping-complete, planning-complete, build-complete, release-readiness certificate
- **4 NEXUS-Micro runbooks**: post-deploy-handoff, sprint-planning, ux-design-sprint, support-escalation
- **12 handoff contracts** added to agents (proposal-strategist, project-shepherd, deal-strategist, feedback-synthesizer, outbound-strategist, requirements-engineer, integration-engineer, lead-finder, debugger, retro-facilitator, test-strategist, qa-triage-lead)
- Pricing and effort estimation workflow in proposal-strategist
- Communication setup section in project-shepherd (channel taxonomy, meeting templates, status reports, escalation matrix)
- Invoicing capabilities in financial-controller (invoice templates, AR aging, payment reminders)
- Contract drafting in legal-compliance-checker (NDAs, SOW terms, open-source license guidance)

### Changed
- **Renamed** `finance-tracker` -> `financial-controller` (support/) -- added Write/Edit tools, invoicing
- **Renamed** `autonomous-optimization-architect` -> `ai-cost-optimizer` (engineering/) -- narrowed to AI cost focus
- **Moved** `workflow-optimizer` from testing/ to project-management/ -- added Write/Edit tools, Lean/Six Sigma focus
- **Moved** `accounts-payable-agent` from specialized/ to support/ -- removed crypto rails, added Stripe
- **Fixed** `incident-response-commander` -- replaced PagerDuty with Alertmanager/Grafana/Loki, simplified escalation for solo founder
- **Fixed** `database-optimizer` -- added ORM awareness, IRL stack specifics, handoff contract
- **Fixed** `outbound-strategist` -- added Write tool, Deal Briefing handoff to deal-strategist
- **Fixed** `analytics-reporter` -- added cross-cutting tag for discoverability
- Cleaned emoji headers from 13 agency-import agents
- Removed `agency-import` tag from 13 customized agents
- Fixed encoding violations (U+2013, U+2014, U+2192) in 7 files

### Removed
- **Retired** `infrastructure-maintainer` (support/) -- merged useful content into infra-engineer

## [agency-1.8.0] - 2026-03-26

### Added
- **Commit guard script** (`scripts/commit_guard.py`) -- data-driven PreToolUse/PostToolUse guard that blocks commits containing files that should be gitignored (build artifacts, dependency directories, secrets, OS junk). Pattern table covers Python, Node, PHP, Ruby, Rust, Java/JVM, .NET, and General ecosystems.
  - `post` subcommand (PostToolUse): warns on stderr after `git add` if staged files match ignored patterns
  - `pre` subcommand (PreToolUse): blocks `git commit` with exit 2 if staged files match ignored patterns
  - `check` subcommand (manual): prints violations and exits 1, or reports clean and exits 0
  - `rules` subcommand: prints the active pattern table grouped by ecosystem
  - Registered `commit_guard.py pre` in PreToolUse Bash hooks (after `version_guard.py`, before `pre-deploy-secrets-sync.sh`)
  - Registered `commit_guard.py post` in PostToolUse Bash hooks (after `auto-tag.py`, before `post-deploy-secrets-verify.sh`)
  - Added `commit-guard` entry to `registry.yaml` scripts section

## [agency-1.7.0] - 2026-03-24

### Added
- **Format files hook** (`scripts/format_files.py`) -- data-driven PostToolUse formatter and PreToolUse guard for Edit/Write tools. Add new formatters or block rules by editing the RULES table -- no hook registration changes needed.
  - PostToolUse: auto-runs `terraform fmt` on `.tf` files after edits
  - PreToolUse: blocks direct edits to lock files (pnpm-lock.yaml, package-lock.json, yarn.lock, uv.lock, composer.lock, Cargo.lock, poetry.lock, Gemfile.lock)
  - Includes `rules` subcommand to print the active rule table for debugging

## [agency-1.6.0] - 2026-03-20

### Added
- **Entropy agent** (`agents/engineering/entropy.md`) -- secrets lifecycle manager that watches Bitwarden, syncs to Ansible Vault/K8s targets, enforces rotation policy, and alerts on drift
- **Secrets-sync skill** (`skills/secrets-sync/`) -- user-invocable workflow for syncing secrets from Bitwarden to infrastructure targets
- **Pre-deploy secrets sync hook** (`hooks/pre-deploy-secrets-sync.sh`) -- PreToolUse hook that triggers secret sync before deployment commands
- **Post-deploy secrets verify hook** (`hooks/post-deploy-secrets-verify.sh`) -- PostToolUse hook that verifies secrets match after deployments

### Changed
- **Orchestrator agent v2** (`agents/core/orchestrator.md`) -- major rewrite adding agent coordination patterns (parallel spawning, background agents, SendMessage continuations, worktree isolation), subagent selection tables, NEXUS integration section, hook compliance awareness, and 6th iron law ("never combine unrelated changes")
- Updated orchestrator registry description to include trigger text for subagent selection
- Updated CLAUDE.md with Entropy agent documentation and engineering division details

## [agency-1.5.0] - 2026-03-19

### Changed
- Grant Agent tool to all 148 agents for universal orchestration -- every agent can now spawn subagents and teams, enabling mesh-style self-organization instead of requiring escalation through managers

## [agency-1.4.1] - 2026-03-19

### Changed
- Grant Agent tool to all 12 managing agents, enabling delegation through the org chart hierarchy: CEO, Orchestrator, CTO, VP of Engineering, DevOps Manager, Incident Response Commander, Studio Producer, Project Shepherd, Studio Operations, Sprint Prioritizer, Sales Coach, Finance Tracker

## [agency-1.4.0] - 2026-03-19

### Added
- **Shared changelog parsing library** (`scripts/_shared/changelog.py`) -- reusable CHANGELOG.md parser following the Apache Commons shared-utilities pattern. Two public functions: `get_latest_changelog_version()` and `has_content_under_header()`.
- **Auto-tag hook** (`scripts/auto-tag.py`) -- PostToolUse hook that detects `gh pr merge` commands and automatically creates + pushes a git tag when CHANGELOG version is ahead of the latest tag. Includes `ci` subcommand for GitHub Actions.
- **Auto-tag GitHub Action** (`.github/workflows/auto-tag.yml`) -- triggers on pushes to main that touch CHANGELOG.md or plugin.json, runs `auto-tag.py ci` to create tags.
- PostToolUse hook registration in hooks.json (14 event types total)

### Changed
- Refactored all 10 scripts to use `_shared/` utility modules (git_ops, dotted, encoding, paths, audit, summon_state)

### Fixed
- `worktree_lifecycle.py` slug computation no longer incorrectly lstrips the leading slash (uses `_shared.paths.cwd_slug`)

## [agency-1.3.0] - 2026-03-18

### Added
- **Shared frontmatter config library** (`scripts/frontmatter_config.py`) -- extracts CLAUDE.md hierarchy resolution into a reusable module (idea 73). Three public functions: `resolve_config()`, `resolve_typed()`, `resolve_frontmatter()`. Deep-merge semantics with last-wins. `home_override` parameter for testing.
- **Instructions guard** (`scripts/instructions-guard.py`) -- InstructionsLoaded hook validating UTF-8 encoding and detecting [PLACEHOLDER] markers when CLAUDE.md/rules files load into context. Advisory only.
- **PostCompact recovery** (`scripts/postcompact-recovery.py`) -- PostCompact hook verifying critical context survived compaction. Checks agent persona and configurable reinject strings against compact summary. Writes audit JSONL.
- **Config tamper guard** (`scripts/config-tamper-guard.py`) -- ConfigChange hook with two-phase design: snapshots settings.json at SessionStart, diffs against cache on ConfigChange. Blocks removal of protected keys (hooks, permissions.deny) via JSON decision format.
- **Worktree lifecycle** (`scripts/worktree_lifecycle.py`) -- WorktreeCreate hook that replaces default worktree creation, propagates git hooks from main repo, checks for .env files. WorktreeRemove hook for audit logging.
- **Stop failure audit** (`scripts/stop-failure-audit.py`) -- StopFailure hook writing structured JSONL audit entries when sessions crash from API errors. Fire-and-forget.
- **Teammate gate** (`scripts/teammate-gate.py`) -- TeammateIdle/TaskCompleted hook validating subagent output. Discovers changed files via git status. Exit 2 for fixable violations (retry), continue:false for security violations (hard stop).
- **Elicitation gate** (`scripts/elicitation-gate.py`) -- Elicitation/ElicitationResult hook for MCP audit logging and optional blocking via hookSpecificOutput action:decline.
- hooks.json expanded from 3 to 13 event types (SessionStart, InstructionsLoaded, PreCompact, PostCompact, ConfigChange, WorktreeCreate, WorktreeRemove, PreToolUse, StopFailure, TeammateIdle, TaskCompleted, Elicitation, ElicitationResult)
- New frontmatter config namespaces: `enforcement`, `compaction`, `worktree`, `audit`, `mcp`
- 46 new tests across 8 test files

### Changed
- `accessibility-config.py` refactored to use shared frontmatter config library (174 -> ~60 lines, no behavior change)

## [agency-1.2.0] - 2026-03-15

### Added
- **Version guard hook** (`scripts/version_guard.py`) -- PreToolUse hook enforcing semver consistency between manifests, git tags, and CHANGELOG on protected branches. Two-tier enforcement: Tier 1 (always on) validates manifest-tag-changelog sync; Tier 2 (opt-in) uses conventional commits to compute expected versions with asymmetric comparison.
- `.version-guard.yaml` config file support for cross-repo portability
- Manifest auto-detection for package.json, pyproject.toml, Cargo.toml, composer.json, and .claude-plugin/plugin.json
- 38 tests covering all enforcement paths
- Implementation plan at `docs/plans/2026-03-15-version-guard-implementation.md`

## [agency-1.1.0] - 2026-03-15

### Added
- **ADHD accessibility skill** (`skills/accessibility-adhd/`) -- behavioral overlay that adapts Claude's communication style with 9 independently configurable behaviors: micro-chunking, reduced decisions, response brevity, momentum preservation, progress dopamine, context anchoring, anti-rabbit-hole guardrails, time awareness, and sensory-friendly formatting
- **`/init-adhd` command** (`commands/init-adhd.md`) -- guided setup wizard for configuring ADHD mode via CLAUDE.md YAML frontmatter
- **Accessibility config detector** (`scripts/accessibility-config.py`) -- parses CLAUDE.md frontmatter for auto-activation via SessionStart hook
- **User guide** (`docs/guides/accessibility-adhd.md`) -- configuration reference, behavior examples, preset recipes, and troubleshooting
- SessionStart hook for automatic ADHD mode detection from CLAUDE.md frontmatter

### Fixed
- Changelog guard now outputs errors to stderr and blocks combined `git add + commit` in a single command
- Removed explicit agent paths from `plugin.json` (uses auto-discovery)
- Fixed `marketplace.json` source path to `./` for schema compliance
- Restored `marketplace.json` for plugin discovery

## [agency-1.0.0] - 2026-03-12

### Changed
- **BREAKING**: Replaced multi-plugin structure (core, engineering, operations, research, finance) with single `infinite-room-labs@agency` plugin
- Reorganized agents into 14 division directories under `agents/` (core, engineering, design, marketing, sales, paid-media, product, project-management, testing, support, research, spatial-computing, game-development, specialized)
- Moved scripts from `plugins/core/scripts/` and `plugins/engineering/scripts/` to `scripts/`
- Moved skills from `plugins/*/skills/` to `skills/`
- Moved commands from `plugins/*/commands/` to `commands/`
- Merged hooks from multiple plugins into single `hooks/hooks.json`
- Updated `summon.py` namespace discovery from `plugins/*/` to `agents/*/` divisions
- Renamed "plugin" terminology to "division" in summon.py and related tools
- Updated `find-agent` command to scan division-based structure

### Added
- **148 specialized agents** (up from 14) across 14 business divisions
- Imported 130+ agents from Agency Agents (MIT) open-source project with IRL frontmatter
- Merged 14 overlapping agents combining IRL governance with Agency personality depth
- **NEXUS orchestration system** replacing `/devops-team`:
  - `/nexus` -- Full 7-phase pipeline for complete product lifecycle
  - `/nexus-sprint` -- Focused 2-6 week feature/MVP builds
  - `/nexus-micro` -- Lightweight 1-5 day tasks with pre-built runbooks
- `strategy/` directory with NEXUS reference material (doctrine, playbooks, runbooks, coordination templates)
- New divisions: design, marketing, sales, paid-media, product, project-management, testing, support, spatial-computing, game-development, specialized
- Core division agents: CEO (merged), Orchestrator, Reality Checker
- PreToolUse hook for changelog-guard (commit protection on protected branches)
- CONTRIBUTING.md with merged agent design guidelines
- Comprehensive README.md with full agent catalog

### Removed
- `plugins/` directory structure (replaced by flat layout)
- `.claude-plugin/marketplace.json` (replaced by single `plugin.json`)
- Individual plugin `plugin.json` files (5 files)
- `/devops-team` skill (replaced by `/nexus`)
- `plugins/operations/TODO.md` and `plugins/finance/TODO.md` (operations and finance agents now in specialized/support divisions)

## [core-0.2.0] - 2026-03-11

### Added
- **SUMMON runtime agent loading system** (`/load-agent`, `/end-agent-session`)
- `summon.py` CLI with 6 subcommands: list, discover, info, validate, state (create/check/clean/delete/reminder)
- `load-agent` skill with multi-phase flow: parse input, discovery, state check, persona injection
- `end-agent-session` skill for clean session teardown
- `load-agent` and `end-agent-session` thin-router commands
- SessionStart hook for stale state cleanup
- PreCompact hook for persona persistence after context compaction
- CLAUDE_SESSION_ID-based staleness detection with 24h TTL fallback
- Dynamic plugin namespace discovery from `plugins/*/` directories
- 35 tests covering all CLI subcommands
- 4 new entries in `registry.yaml` (2 skills, 2 commands)
