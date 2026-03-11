# Changelog

All notable changes to the agent-ops marketplace will be documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/).

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
