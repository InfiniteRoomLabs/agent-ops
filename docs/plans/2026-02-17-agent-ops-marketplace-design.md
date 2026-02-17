# agent-ops Marketplace Design

**Date**: 2026-02-17
**Status**: Approved

## Summary

`agent-ops` is a private Claude Code marketplace for Infinite Room Labs. It hosts plugins that provide agents, skills, commands, and hooks for running the business. Components are organized into domain-specific plugins and tagged with business function, scenario, and freeform labels for discovery.

## Architecture

- **Marketplace repo**: `InfiniteRoomLabs/agent-ops` on GitHub (private)
- **Manifest**: `.claude-plugin/marketplace.json` catalogs all plugins
- **Plugin layout**: Each plugin lives under `plugins/{domain}/` with standard Claude Code plugin structure
- **Discovery**: Claude Code auto-discovers components within each installed plugin. Cross-plugin search via frontmatter tags and `registry.yaml`.

## Plugins

| Plugin | Purpose |
|--------|---------|
| `core` | Cross-cutting utilities, shared skills, tag search commands |
| `engineering` | Infrastructure, CI/CD, code quality, developer tooling |
| `operations` | Business ops, vendor management, scheduling, process automation |
| `research` | Market analysis, competitive intelligence, technology evaluation |
| `finance` | Bookkeeping, invoicing, expense tracking |

## Tagging Scheme

All agents, skills, and commands use YAML frontmatter with these custom fields:

```yaml
tags:
  function: [engineering, operations]    # business function (who uses it)
  scenario: [domain-onboarding]          # workflow (when to use it)
  custom: [dns, registrar]              # freeform labels
```

Claude Code ignores unrecognized frontmatter fields, so these are safe extensions.

## Cross-Repo Integration

Each company repo can auto-prompt marketplace installation via `.claude/settings.json`:

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

## Growth Path

- Start with `core` + four domain plugins (mostly templates)
- Populate agents/skills as needs arise
- Split plugins into separate repos if they outgrow this monorepo
- Marketplace manifest stays the catalog regardless of where plugins live
