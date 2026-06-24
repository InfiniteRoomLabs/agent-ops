# Infinite Room Labs Agency

A Claude Code plugin for running a software company with AI agents. It bundles 156+ specialized agent roles with a layer of guardrail hooks and reusable engineering workflows.

It packages the agents, skills, commands, and enforcement hooks Infinite Room Labs uses internally. The pieces work independently: run the guardrail hooks without the agents, or load an agent without the orchestration.

## Quick Start

```bash
# Install
/plugin install agency@infinite-room-labs

# Find an agent, skill, or command by keyword or tag
/find-agent security review

# Load a specialist as your session persona
/load-agent backend-architect

# Run a workflow skill
/code-review <PR URL or diff>
```

Experimental: `/nexus`, `/nexus-sprint`, and `/nexus-micro` coordinate multiple
agents across a project. They work today but are the least settled part of the
plugin; see [Features](#features).

## Features

### Specialized agents

156+ agents across 14 divisions, from engineering and design through game development and spatial computing. Each one carries a focused system prompt and a scoped tool set, pinned to a model tier. Browse the full [Agent Catalog](#agent-catalog) below, or search by tag or keyword with `/find-agent`.

### Guardrail hooks

The plugin ships Python hooks that enforce repository hygiene while you work. They run on Claude Code's hook events and fail safe, so a malformed payload never blocks you.

| Hook | Runs on | Enforces |
|------|---------|----------|
| version-guard | commit | semver stays consistent across manifests, tags, and CHANGELOG on protected branches |
| changelog-guard | commit | protected-branch commits include a CHANGELOG update |
| commit-guard | git add / commit | staged files don't match gitignored or secret patterns |
| config-tamper-guard | settings change | protected settings stay append-only; silent weakening is blocked |
| test-coverage-guard | commit | a new `scripts/*.py` ships with its `tests/test_*.py` |
| teammate-gate | subagent finish | subagent output passes encoding, env-file, and agent-directory checks |

Beyond the table, the suite handles UTF-8 validation, worktree setup, post-compaction recovery, and release auto-tagging. Every hook has tests, and the suite runs in CI.

### Workflow skills and commands

26 invocable skills cover recurring engineering work: architecture decisions, code review, debugging, dependency audits, release prep, incident response, testing strategy, and public-release readiness. Five slash commands handle discovery and packaging. See [Skills](#skills) and [Commands](#commands).

### Output styles

Activate a shipped output style per session or per project, such as an ADHD-friendly mode that chunks work into small steps and tracks progress. See [Output Styles](#output-styles).

### Experimental: orchestration and personas

`/nexus` and its `-sprint` and `-micro` variants coordinate teams of agents across a project, and the persona loader (`/load-agent`, `/end-agent-session`) makes one agent your session voice. Both work today, but they are the least settled part of the plugin and their shape may change.

## Agent Catalog

### Core (3 agents)

| Agent | Model | Role |
|-------|-------|------|
| CEO | opus | Strategic leadership, founding principles, cross-division coordination |
| Orchestrator | opus | Multi-agent pipeline coordinator (NEXUS) |
| Reality Checker | opus | Final quality authority, evidence-based validation |

### Engineering (28 agents)

| Agent | Model | Role |
|-------|-------|------|
| CTO | opus | Strategic technology leadership, architecture decisions |
| VP Engineering | opus | Standards enforcement, cross-team coordination |
| DevOps Manager | sonnet | Task assignment, deployment coordination |
| Security Lead | sonnet | Security review gate, threat modeling |
| Infrastructure Engineer | sonnet | Terraform, Terragrunt, IaC |
| CI/CD Engineer | sonnet | GitHub Actions, build pipelines |
| Platform Engineer | sonnet | Cloudflare, DNS, CDN |
| Code Reviewer | sonnet | Code and infrastructure review |
| OSS Health Checker | sonnet | Open source readiness audits |
| Frontend Developer | sonnet | React, Vue, Angular, web apps |
| Backend Architect | sonnet | System design, APIs, databases |
| AI Engineer | sonnet | ML models, AI integration |
| Senior Developer | sonnet | Full-stack implementation |
| Mobile App Builder | sonnet | iOS, Android, cross-platform |
| Rapid Prototyper | sonnet | Fast MVP and PoC creation |
| Database Optimizer | sonnet | Query optimization, schema design |
| Data Engineer | sonnet | Data pipelines, ETL |
| Technical Writer | sonnet | Documentation, API references |
| Git Workflow Master | sonnet | Git strategy, branching models |
| Incident Response Commander | sonnet | Production incident management |
| Solidity Smart Contract Engineer | sonnet | Blockchain, smart contracts |
| Threat Detection Engineer | sonnet | Security monitoring, threat hunting |
| Embedded Firmware Engineer | sonnet | IoT, firmware, embedded systems |
| Autonomous Optimization Architect | sonnet | Self-optimizing systems |
| Feishu Integration Developer | sonnet | Feishu/Lark platform integration |
| WeChat Mini Program Developer | sonnet | WeChat mini program development |
| Infrastructure Intern | haiku | Infra scaffolding, research |
| CI/CD Intern | haiku | CI/CD validation, documentation |

### Design (8 agents)

| Agent | Model | Role |
|-------|-------|------|
| UI Designer | sonnet | Visual design systems, component libraries |
| UX Architect | sonnet | Information architecture, interaction design |
| UX Researcher | sonnet | User research, usability testing |
| Brand Guardian | sonnet | Brand identity, consistency |
| Visual Storyteller | sonnet | Visual narratives, multimedia content |
| Image Prompt Engineer | sonnet | AI image generation prompts |
| Inclusive Visuals Specialist | sonnet | Accessible, diverse visual design |
| Whimsy Injector | sonnet | Personality, delight, playful elements |

### Marketing (26 agents)

| Agent | Model | Role |
|-------|-------|------|
| Growth Hacker | sonnet | Data-driven user acquisition |
| Content Creator | sonnet | Multi-platform content campaigns |
| Social Media Strategist | sonnet | Cross-platform social strategy |
| SEO Specialist | sonnet | Search engine optimization |
| Twitter Engager | sonnet | Twitter/X engagement and growth |
| TikTok Strategist | sonnet | Short-form video strategy |
| Instagram Curator | sonnet | Visual social media curation |
| Reddit Community Builder | sonnet | Reddit engagement and communities |
| LinkedIn Content Creator | sonnet | Professional network content |
| Podcast Strategist | sonnet | Podcast production and growth |
| App Store Optimizer | sonnet | ASO, app discoverability |
| Book Co-Author | sonnet | Book writing collaboration |
| Carousel Growth Engine | sonnet | Carousel content strategy |
| Baidu SEO Specialist | sonnet | Chinese search optimization |
| Bilibili Content Strategist | sonnet | Bilibili platform strategy |
| Douyin Strategist | sonnet | Chinese TikTok (Douyin) strategy |
| Kuaishou Strategist | sonnet | Kuaishou platform strategy |
| WeChat Official Account | sonnet | WeChat content management |
| Weibo Strategist | sonnet | Weibo platform strategy |
| Xiaohongshu Specialist | sonnet | Xiaohongshu (Little Red Book) strategy |
| Zhihu Strategist | sonnet | Zhihu Q&A platform strategy |
| Livestream Commerce Coach | sonnet | Live selling strategy |
| Short Video Editing Coach | sonnet | Short-form video production |
| China E-Commerce Operator | sonnet | Chinese e-commerce operations |
| Cross-Border E-Commerce | sonnet | International e-commerce |
| Private Domain Operator | sonnet | WeChat private traffic |

### Sales (8 agents)

| Agent | Model | Role |
|-------|-------|------|
| Account Strategist | sonnet | Account management and growth |
| Sales Coach | sonnet | Sales team training and enablement |
| Deal Strategist | sonnet | Deal structure and negotiation |
| Discovery Coach | sonnet | Discovery call methodology |
| Sales Engineer | sonnet | Technical sales support |
| Outbound Strategist | sonnet | Outbound prospecting |
| Pipeline Analyst | sonnet | Pipeline analytics and forecasting |
| Proposal Strategist | sonnet | Proposal writing and strategy |

### Paid Media (7 agents)

| Agent | Model | Role |
|-------|-------|------|
| PPC Strategist | sonnet | Pay-per-click campaign management |
| Paid Social Strategist | sonnet | Paid social media advertising |
| Programmatic Buyer | sonnet | Programmatic ad buying |
| Creative Strategist | sonnet | Ad creative strategy |
| Auditor | sonnet | Ad spend and performance auditing |
| Search Query Analyst | sonnet | Search query optimization |
| Tracking Specialist | sonnet | Ad tracking and attribution |

### Product (3 agents)

| Agent | Model | Role |
|-------|-------|------|
| Sprint Prioritizer | sonnet | Agile sprint planning, RICE scoring |
| Feedback Synthesizer | sonnet | User feedback analysis |
| Behavioral Nudge Engine | sonnet | Behavioral design patterns |

### Project Management (5 agents)

| Agent | Model | Role |
|-------|-------|------|
| Studio Producer | sonnet | Portfolio-level orchestration |
| Project Shepherd | sonnet | Cross-functional coordination |
| Studio Operations | sonnet | Day-to-day process optimization |
| Experiment Tracker | sonnet | A/B testing and experiments |
| Jira Workflow Steward | sonnet | Jira workflow management |

### Testing (6 agents)

| Agent | Model | Role |
|-------|-------|------|
| Evidence Collector | sonnet | Screenshot-based QA validation |
| Test Results Analyzer | sonnet | Test evaluation and metrics |
| Performance Benchmarker | sonnet | Performance measurement |
| API Tester | sonnet | API validation and testing |
| Accessibility Auditor | sonnet | WCAG compliance testing |
| Workflow Optimizer | sonnet | Process improvement |

### Support (6 agents)

| Agent | Model | Role |
|-------|-------|------|
| Support Responder | sonnet | Customer service and issue resolution |
| Analytics Reporter | sonnet | Data analysis and dashboards |
| Finance Tracker | sonnet | Financial planning and tracking |
| Infrastructure Maintainer | sonnet | System reliability and operations |
| Legal Compliance Checker | sonnet | Legal and regulatory compliance |
| Executive Summary Generator | sonnet | Stakeholder report generation |

### Research (2 agents)

| Agent | Model | Role |
|-------|-------|------|
| Competitor Scanner | sonnet | Competitive intelligence |
| Tech Evaluator | sonnet | Technology comparison and evaluation |

### Spatial Computing (6 agents)

| Agent | Model | Role |
|-------|-------|------|
| XR Interface Architect | sonnet | Spatial interaction design |
| XR Immersive Developer | sonnet | WebXR and immersive tech |
| visionOS Spatial Engineer | sonnet | Apple visionOS development |
| macOS Spatial Metal Engineer | sonnet | Metal and spatial computing on macOS |
| XR Cockpit Interaction Specialist | sonnet | Cockpit-based control systems |
| Terminal Integration Specialist | sonnet | Terminal and CLI integration for XR |

### Game Development (19 agents)

| Agent | Model | Role |
|-------|-------|------|
| Game Designer | sonnet | Core game design and mechanics |
| Level Designer | sonnet | Level and environment design |
| Narrative Designer | sonnet | Story, dialogue, world-building |
| Technical Artist | sonnet | Art pipeline and shader development |
| Game Audio Engineer | sonnet | Audio systems and sound design |
| Unity Architect | sonnet | Unity architecture and systems |
| Unity Shader Graph Artist | sonnet | Unity shader development |
| Unity Multiplayer Engineer | sonnet | Unity networking and multiplayer |
| Unity Editor Tool Developer | sonnet | Unity editor extensions |
| Unreal Systems Engineer | sonnet | Unreal Engine systems |
| Unreal World Builder | sonnet | Unreal environment creation |
| Unreal Technical Artist | sonnet | Unreal art pipeline |
| Unreal Multiplayer Architect | sonnet | Unreal networking |
| Godot Gameplay Scripter | sonnet | Godot GDScript development |
| Godot Shader Developer | sonnet | Godot shader programming |
| Godot Multiplayer Engineer | sonnet | Godot networking |
| Roblox Experience Designer | sonnet | Roblox experience design |
| Roblox Systems Scripter | sonnet | Roblox Lua scripting |
| Roblox Avatar Creator | sonnet | Roblox avatar systems |

### Specialized (21 agents)

| Agent | Model | Role |
|-------|-------|------|
| Developer Advocate | sonnet | Developer relations and advocacy |
| MCP Builder | sonnet | Model Context Protocol server development |
| Document Generator | sonnet | Automated document creation |
| Model QA | sonnet | AI model quality assurance |
| Cultural Intelligence Strategist | sonnet | Cross-cultural business strategy |
| LSP Index Engineer | sonnet | Language server protocol development |
| Blockchain Security Auditor | sonnet | Smart contract security |
| Compliance Auditor | sonnet | Regulatory compliance |
| Accounts Payable Agent | sonnet | Invoice processing automation |
| Data Consolidation Agent | sonnet | Data integration and consolidation |
| Sales Data Extraction Agent | sonnet | CRM data extraction |
| Report Distribution Agent | sonnet | Automated report delivery |
| Identity Graph Operator | sonnet | Identity resolution and matching |
| Agentic Identity Trust | sonnet | AI identity and trust frameworks |
| Corporate Training Designer | sonnet | Training program development |
| Healthcare Marketing Compliance | sonnet | Healthcare marketing regulations |
| Government Digital Presales Consultant | sonnet | Government technology consulting |
| Study Abroad Advisor | sonnet | International education guidance |
| Recruitment Specialist | sonnet | Talent acquisition and hiring |
| Supply Chain Strategist | sonnet | Supply chain optimization |
| ZK Steward | sonnet | Zettelkasten-style knowledge-base management |

## Skills

26 skills you invoke with a slash command. Each is a focused workflow.

**Engineering and delivery**

| Skill | Purpose |
|-------|---------|
| `/architecture` | Create or evaluate an architecture decision record (ADR) |
| `/system-design` | Design a system, service, or API |
| `/code-review` | Review a change for security, performance, and correctness |
| `/debug` | Reproduce, isolate, diagnose, and fix a bug |
| `/testing-strategy` | Design a test strategy and plan |
| `/tech-debt` | Identify and prioritize technical debt |
| `/dep-audit` | Audit dependencies for license, security, and staleness |
| `/documentation` | Write and maintain technical documentation |
| `/tsdoc` | Write or fix TypeScript doc comments (TSDoc) |
| `/deploy-checklist` | Verify readiness before shipping |
| `/release-prep` | Run a version bump, CHANGELOG, tag, and release |
| `/incident-response` | Triage, communicate, and write a postmortem |

**Repository, research, and meta**

| Skill | Purpose |
|-------|---------|
| `/new-agent` | Scaffold a new agent, skill, or command |
| `/project-onboard` | Set up a repo with IRL conventions |
| `/public-readiness` | Audit a repo before making it public (leaks, license, history scrub) |
| `/secrets-sync` | Sync secrets from Bitwarden to Ansible Vault and Kubernetes |
| `/prompt-refiner` | Restructure a vague prompt into clear instructions |
| `/persona-forge` | Generate and refine a purpose-built persona for a task |
| `/render-mermaid` | Render a mermaid diagram to an image or PDF |
| `/market-scan` | Analyze a market segment and its competitors |
| `/standup` | Generate a standup update from recent activity |

**Personas and orchestration (experimental)**

| Skill | Purpose |
|-------|---------|
| `/load-agent` | Load an agent as your session persona |
| `/end-agent-session` | Unload the active persona |
| `/nexus` | Coordinate all divisions across a full project lifecycle |
| `/nexus-sprint` | Build a feature or MVP with a focused team |
| `/nexus-micro` | Run a quick 1-5 day task with a runbook |

## Commands

| Command | Description |
|---------|-------------|
| `/find-agent` | Search agents, skills, commands by tag or keyword |
| `/load-agent` | Router to load-agent skill |
| `/end-agent-session` | Router to end-agent-session skill |
| `/publish-package` | Package publishing workflow |
| `/trend-watch` | Quick trend check for technologies/markets |

## Output Styles

The plugin ships output styles from `output-styles/` (declared via `outputStyles` in `.claude-plugin/plugin.json`).

| Style | Description |
|-------|-------------|
| `agency:ADHD Accessibility` | ADHD-friendly communication: micro-chunking, reduced decisions, momentum preservation, progress tracking |

### Registering an Output Style

Plugin-shipped styles register under a **plugin-namespaced name** (`agency:<style name>`). The plain style name only matches files in `~/.claude/output-styles/`. If the name does not resolve, Claude Code silently falls back to the default style with no warning.

Activate from inside a session (persists to settings):

```
/output-style agency:ADHD Accessibility
```

Or set it directly in `~/.claude/settings.json`:

```json
{
  "outputStyle": "agency:ADHD Accessibility"
}
```

Two gotchas:

- **Use the namespaced name.** `"outputStyle": "ADHD Accessibility"` (no `agency:` prefix) silently resolves to the default style.
- **Project settings override user settings.** An `outputStyle` key in a repo's `.claude/settings.local.json` or `.claude/settings.json` beats the user-level setting in that repo. Remove it if the style mysteriously stays off in one project.

Output styles resolve at session start, so restart the session after changing the setting.

## Architecture

This repo is a single plugin. Claude Code loads every agent definition under `agents/`, grouped by division. The SUMMON system (`scripts/summon.py`) handles runtime persona loading and session state.

NEXUS orchestration is implemented as skills rather than agents, providing three deployment scales (Full/Sprint/Micro) with reference material in `strategy/`.

## Testing

Run `uv run pytest`. Conventions, the testing standards, and manual end-to-end checks are documented in [`TESTING.md`](TESTING.md).

## Origins

This agency merges two sources:
- **IRL agent-ops** (v0.2.x): Governance infrastructure, Iron Laws, SUMMON system, DevOps org chart
- **Agency Agents** (MIT): 142+ battle-tested agent personalities across 12 business divisions with NEXUS orchestration

## License

MIT. See [LICENSE](LICENSE). Agent personalities are derived from the upstream
Agency Agents project, also MIT-licensed (see Origins above).
