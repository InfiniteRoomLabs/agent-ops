---
name: project-onboard
description: Use when setting up a new repository or project with Infinite Room Labs conventions and marketplace integration
tags:
  function: [engineering, operations]
  scenario: [project-setup]
  custom: [onboarding, conventions, marketplace]
---

# Project Onboard

Set up a new repository with Infinite Room Labs conventions, marketplace integration, and standard tooling.

## Process

1. Confirm the project name, language/framework, and whether it will be open source
2. Create or verify the directory structure appropriate for the project type
3. Apply the standard configuration files listed below
4. Verify everything is in place

## Standard Configuration

### `.claude/settings.json` -- Marketplace Integration

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

### `CLAUDE.md` -- Project Instructions

Create a CLAUDE.md following the quality criteria from claude-md-management. At minimum include:

- What the project is (1-2 sentences)
- Primary language and framework
- Build/test/lint commands
- Directory structure overview
- Key conventions (naming, patterns, architecture decisions)

### `.gitignore` -- Language-Appropriate Ignores

Generate based on project type. Always include:

```
# Agent runtime directories
.claude/
.codex/
.gemini/
.cursor/

# Environment
.env
.env.local
```

### `.claudeignore` -- Agent Boundary

Include at minimum:

```
.claude/
.git/
node_modules/
dist/
build/
__pycache__/
```

### Open Source Files (if applicable)

If the project is open source, verify or create:

- `LICENSE` -- MIT unless the user specifies otherwise
- `CONTRIBUTING.md` -- basic contribution guidelines
- `CHANGELOG.md` -- initialized with Keep a Changelog format
- `.github/ISSUE_TEMPLATE/` -- bug report and feature request templates
- `.github/PULL_REQUEST_TEMPLATE.md`

## After Onboarding

Report what was created and suggest next steps:
- Install marketplace plugins: `/plugin marketplace add InfiniteRoomLabs/agent-ops`
- Run claude-automation-recommender for additional setup suggestions
- Start first feature with superpowers:brainstorming

## Anti-Patterns

- Do NOT add configuration the project does not need yet (YAGNI)
- Do NOT install dependencies -- only create configuration files
- Do NOT assume a specific CI/CD provider -- ask the user
- Do NOT create a README with placeholder content -- either write a real one or skip it
