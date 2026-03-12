# Contributing to Infinite Room Labs Agency

## How to Contribute

### 1. Create a New Agent

1. Choose the appropriate division directory under `agents/`
2. Create your agent file following the template below
3. Test the agent in real scenarios
4. Update `registry.yaml`
5. Submit a Pull Request

### 2. Improve Existing Agents

- Add real-world examples and use cases
- Enhance code samples with modern patterns
- Update workflows based on new best practices
- Fix typos, improve clarity

### 3. Report Issues

- Check if the issue already exists
- Provide clear reproduction steps
- Include context about your use case

## Agent Design Guidelines

### Required Frontmatter

Every agent MUST have this frontmatter:

```yaml
---
description: One-line trigger text that tells Claude Code when to spawn this agent
model: sonnet                          # opus | sonnet | haiku
tools: Glob, Grep, Read, LS           # comma-separated tool access
color: cyan                            # visual indicator
tags:
  function: [engineering]              # business function
  scenario: [code-review]             # workflow context
  custom: [terraform]                  # freeform labels
---
```

### Model Tier Assignment

| Tier | When to Use |
|------|-------------|
| opus | Executives, orchestrators, agents making architectural decisions |
| sonnet | Most specialists -- the default tier |
| haiku | Interns, simple validation tasks, research lookups |

### Tool Assignment

| Agent Type | Tools |
|-----------|-------|
| Read-only (reviewers, analysts) | Glob, Grep, Read, LS, WebSearch, WebFetch |
| Writing (developers, engineers) | Glob, Grep, Read, LS, Write, Edit, Bash |
| Web-focused (marketing, sales) | Glob, Grep, Read, LS, WebSearch, WebFetch |
| Advisory (coaches, mentors) | Read, WebSearch, WebFetch |

### Agent Body Structure

Agents have two semantic groups:

**Persona (who the agent is)**
- Identity & role description
- Communication style and personality
- Iron Laws / critical rules / constraints

**Operations (what the agent does)**
- Core mission and responsibilities
- Technical deliverables with code examples
- Workflow process (step-by-step)
- Success metrics (measurable outcomes)
- Advanced capabilities

### IRL-Specific Conventions

For agents in the IRL governance chain (core/ and engineering/):

1. **Iron Laws** -- Non-negotiable behavioral constraints. Place after the opening paragraph.
2. **Reference Material** -- Paths to relevant repos, docs, and configs.
3. **Delegation Pattern** -- Who they report to, who reports to them.
4. **Communication Style** -- Structured format for status reports.

### What Makes a Great Agent

**Great agents have**:
- Narrow, deep specialization
- Distinct personality and voice
- Concrete code/template examples
- Measurable success metrics
- Step-by-step workflows

**Avoid**:
- Generic "helpful assistant" personality
- Vague descriptions without specifics
- No code examples or deliverables
- Overly broad scope
- Untested theoretical approaches

## File Naming

- Use kebab-case: `frontend-developer.md`, `growth-hacker.md`
- No division prefix in filename (the directory provides context)
- For game engine agents, prefix with engine: `unity-architect.md`, `godot-gameplay-scripter.md`

## Tagging

**Function tags** (who uses it):
- `engineering` -- technical roles
- `creative` -- design and content roles
- `revenue` -- sales and marketing roles
- `operations` -- PM, support, ops roles
- `research` -- analysis and evaluation roles
- `executive` -- leadership roles
- `finance` -- financial roles

**Scenario tags** -- workflow contexts when the agent is useful (kebab-case)

**Custom tags** -- freeform labels for discovery (kebab-case)

## Pull Request Process

1. **Test your agent** in real scenarios
2. **Follow the template** above
3. **Update registry.yaml** with the new entry
4. **Submit a PR** with:
   - Clear title: "Add [Agent Name] to [Division]"
   - Description of what the agent does
   - Testing you've done

## File Encoding

**UTF-8 only.** No smart quotes, em dashes, or copy-pasted Office characters. Use ASCII equivalents.

## Git Discipline

- Imperative mood commit messages
- Never rewrite shared branch history
- Never commit secrets or credentials
- Update CHANGELOG.md for any user-facing changes
