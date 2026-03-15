# Changelog

All notable changes to the agent-ops marketplace will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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
