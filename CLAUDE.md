# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Infinite Room Labs AI Agency -- a single Claude Code plugin providing 148+ specialized agents with NEXUS multi-agent orchestration. This is the company's private marketplace for running the business through AI agent teams.

## Repository Structure

Single plugin: `infinite-room-labs@agency`. All components live at the repo root.

```
.claude-plugin/plugin.json        # plugin manifest with agent directory declarations
agents/                            # 148+ agent definitions organized by division
  core/                            # CEO, Orchestrator, Reality Checker
  engineering/                     # CTO, VP Eng, DevOps chain + imported specialists
  design/                          # UI, UX, brand, visual specialists
  marketing/                       # Growth, content, social media, SEO specialists
  sales/                           # Account strategy, pipeline, outbound specialists
  paid-media/                      # PPC, programmatic, social ads specialists
  product/                         # Sprint planning, feedback, behavioral design
  project-management/              # Studio production, project shepherding, experiments
  testing/                         # Evidence collection, benchmarking, API testing
  support/                         # Analytics, finance, infrastructure, legal, support
  research/                        # Competitive intelligence, tech evaluation
  spatial-computing/               # XR, visionOS, Metal, immersive specialists
  game-development/                # Unity, Unreal, Godot, Roblox, narrative design
  specialized/                     # Cross-cutting: compliance, blockchain, data, MCP
skills/                            # 11 user-invocable workflows
  nexus/                           # Full multi-agent orchestration (replaces devops-team)
  nexus-sprint/                    # 2-6 week feature/MVP builds
  nexus-micro/                     # 1-5 day tasks with pre-built runbooks
  load-agent/                      # SUMMON agent persona loading
  end-agent-session/               # SUMMON session teardown
  new-agent/                       # Agent scaffolding
  project-onboard/                 # Repository onboarding
  prompt-refiner/                  # Prompt improvement workflow
  release-prep/                    # Release cycle management
  dep-audit/                       # Dependency auditing
  market-scan/                     # Market research
commands/                          # 5 slash commands
  find-agent.md                    # Tag-based agent/skill/command search
  load-agent.md                    # Agent loading command
  end-agent-session.md             # Session cleanup
  publish-package.md               # Package publishing workflow
  trend-watch.md                   # Trend monitoring
hooks/hooks.json                   # SessionStart, PreCompact, PreToolUse hooks
scripts/
  summon.py                        # Agent discovery & session state CLI
  changelog-guard.py               # Commit protection for CHANGELOG
strategy/                          # NEXUS reference material
  nexus-strategy.md                # Full orchestration doctrine
  playbooks/                       # Phase 0-6 playbooks
  coordination/                    # Handoff templates, activation prompts
  runbooks/                        # Scenario-specific execution guides
registry.yaml                     # Master index of all components
```

## Agent Frontmatter Schema

All agents use this extended frontmatter:

```yaml
---
description: {string}              # Required: trigger text for Claude Code agent selection
model: {opus|sonnet|haiku}         # Required: model tier
tools: {comma-separated list}      # Required: tool access
color: {hex or color name}         # Required: visual indicator
tags:
  function: [{enum list}]          # engineering, operations, finance, research, executive, revenue, creative
  scenario: [{kebab-case list}]    # workflow contexts
  custom: [{kebab-case list}]      # freeform labels
---
```

## Model Tiers

| Tier | Use Case | Agents |
|------|----------|--------|
| opus | Executives, orchestrators, final quality gates | CEO, CTO, VP Eng, Orchestrator, Reality Checker |
| sonnet | Mid-level specialists (default for most agents) | Engineers, designers, marketers, analysts |
| haiku | Simple tasks, research, validation | Interns, basic lookups |

## NEXUS Orchestration

NEXUS replaces the old `/devops-team` skill with universal multi-agent orchestration:

| Mode | Skill | Agents | Timeline | Use Case |
|------|-------|--------|----------|----------|
| Full | `/nexus` | All | 12-24 weeks | Complete product lifecycle |
| Sprint | `/nexus-sprint` | 15-25 | 2-6 weeks | Feature/MVP builds |
| Micro | `/nexus-micro` | 5-10 | 1-5 days | Specific tasks (bug fix, campaign, audit) |

## Tagging Convention

**Standard function values**: engineering, operations, finance, research, executive, revenue, creative

**Scenario and custom tags**: freeform, use kebab-case

## Adding Components

Use the `new-agent` skill, or manually:

1. Create the file in the correct division directory under `agents/`
2. Include YAML frontmatter with `description`, `model`, `tools`, `color`, and `tags`
3. Update `registry.yaml` at the repo root
4. If adding a new division, update the `agents` array in `.claude-plugin/plugin.json`

## Installation

```bash
# Install the agency plugin
/plugin install agency@infinite-room-labs
```

## Cross-Repo Integration

Add to any company repo's `.claude/settings.json`:

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
