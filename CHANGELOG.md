# Changelog

All notable changes to the agent-ops marketplace will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
