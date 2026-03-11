---
name: load-agent
description: Load an agent-ops agent as the primary session persona
allowed-tools: Read, Glob, Grep, Bash
tags:
  function: [engineering, operations, finance, research, executive]
  scenario: [agent-loading, session-management]
  custom: [summon, persona, runtime]
---

# /load-agent

Load an agent-ops agent as the primary session persona using the SUMMON system.

## Usage

```
/load-agent [namespace] <agent-name>
/load-agent --list
/load-agent --info <agent-name>
```

## Arguments

```text
$ARGUMENTS
```

## Instructions

Invoke the `load-agent` skill from the `core` plugin to handle this request. Pass the arguments above directly to the skill.
