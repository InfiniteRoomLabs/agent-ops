---
name: find-agent
description: Search for agents, skills, and commands by tag across all installed plugins
allowed-tools: Read, Glob, Grep
---

# Find Agent

Search the agent-ops marketplace for agents, skills, and commands matching a tag or keyword.

## User Input

```text
$ARGUMENTS
```

## Process

1. Read `registry.yaml` from the agent-ops repo root if available
2. If no registry or the search term is not found there, scan all installed plugin directories:
   - `plugins/*/agents/*.md`
   - `plugins/*/skills/*/SKILL.md`
   - `plugins/*/commands/*.md`
3. Parse YAML frontmatter from each file
4. Match against the search term in: `tags.function`, `tags.scenario`, `tags.custom`, `description`, and `name`
5. Present results grouped by type (agents, skills, commands) with:
   - Name and description
   - Tags
   - Which plugin it belongs to
