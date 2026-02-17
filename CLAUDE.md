# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Private Claude Code marketplace for Infinite Room Labs. Contains plugins that provide agents, skills, commands, and hooks for running the business. Components are organized into domain-specific plugins and tagged by business function, scenario, and freeform labels.

## Repository Structure

This is a Claude Code marketplace repo. The marketplace manifest at `.claude-plugin/marketplace.json` catalogs all plugins. Each plugin lives under `plugins/{domain}/` with standard Claude Code plugin structure.

```
.claude-plugin/marketplace.json    # marketplace catalog
plugins/
  core/                            # cross-cutting utilities and discovery
  engineering/                     # infra, CI/CD, code quality, devtools
  operations/                      # business ops, vendors, scheduling
  research/                        # market analysis, competitive intel
  finance/                         # bookkeeping, invoicing, expenses
```

Each plugin follows the standard layout:
```
plugins/{domain}/
  .claude-plugin/plugin.json       # plugin manifest
  agents/                          # subagent definitions (.md with frontmatter)
  skills/                          # skill directories (each has SKILL.md)
  commands/                        # slash commands (.md with frontmatter)
  hooks/hooks.json                 # event handlers (if any)
  scripts/                         # shared utilities
```

## Tagging Convention

All agents, skills, and commands include these custom frontmatter fields:

```yaml
tags:
  function: [engineering, operations]  # business function (who uses it)
  scenario: [domain-onboarding]        # workflow context (when to use it)
  custom: [dns, registrar]            # freeform labels
```

**Standard function values**: engineering, operations, finance, research, executive
**Scenario and custom tags**: freeform, use kebab-case

## Adding Components

Use the `new-agent` skill from the core plugin, or manually:

1. Create the file in the correct plugin's directory (agents/, skills/, or commands/)
2. Include YAML frontmatter with `description` and `tags`
3. Update `registry.yaml` at the repo root

## Installation

```bash
# Add the marketplace
/plugin marketplace add InfiniteRoomLabs/agent-ops

# Install a plugin
/plugin install core@infinite-room-labs
/plugin install engineering@infinite-room-labs
```

## Cross-Repo Integration

Add to any company repo's `.claude/settings.json` to auto-prompt marketplace installation:

```json
{
  "extraKnownMarketplaces": {
    "infinite-room-labs": {
      "source": {
        "source": "github",
        "repo": "InfiniteRoomLabs/agent-ops"
      }
    }
  }
}
```
