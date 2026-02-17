---
name: new-agent
description: Use when creating a new agent, skill, or command in the agent-ops marketplace
allowed-tools: Read, Write, Glob, Grep
tags:
  function: [engineering, operations, finance, research]
  scenario: [agent-development]
  custom: [scaffolding, templates]
---

# Create New Agent/Skill/Command

Use this skill when someone needs to create a new agent, skill, or command in the agent-ops marketplace.

## Process

1. Ask which plugin it belongs in: core, engineering, operations, research, or finance
2. Ask what type: agent, skill, or command
3. Ask for a name (kebab-case) and brief description
4. Ask for tags:
   - **function**: business functions that use this (engineering, operations, finance, research, executive)
   - **scenario**: workflows where this applies (e.g., domain-onboarding, vendor-evaluation)
   - **custom**: freeform labels
5. Scaffold the component using the templates below

## Agent Template

Create `plugins/{plugin}/agents/{name}.md`:

```markdown
---
description: {description}
tags:
  function: [{functions}]
  scenario: [{scenarios}]
  custom: [{custom}]
---

{System prompt and instructions}
```

## Skill Template

Create `plugins/{plugin}/skills/{name}/SKILL.md`:

```markdown
---
name: {name}
description: {description}
tags:
  function: [{functions}]
  scenario: [{scenarios}]
  custom: [{custom}]
---

{Skill instructions}
```

## Command Template

Create `plugins/{plugin}/commands/{name}.md`:

```markdown
---
name: {name}
description: {description}
tags:
  function: [{functions}]
  scenario: [{scenarios}]
  custom: [{custom}]
---

{Command instructions}
```

## After Scaffolding

Remind the user to update `registry.yaml` at the repo root if it exists.
