---
name: end-agent-session
description: >
  Use when the user wants to unload a currently active agent persona and
  return to the default orchestrator. Clears the agent's behavioral overlay
  and announces the transition.
allowed-tools: Read, Bash
tags:
  function: [engineering, operations, finance, research, executive]
  scenario: [agent-loading, session-management]
  custom: [summon, teardown, persona]
---

# End Agent Session

Unload the currently active SUMMON agent persona and return to the default orchestrator. Clears the behavioral overlay and confirms the transition in a neutral tone.

## User Input

```
$ARGUMENTS
```

No arguments are expected. If arguments are provided, ignore them and proceed with the teardown flow.

## Phase 1: Check State

Run the state check command:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state check
```

- If no agent is currently active, inform the user that no agent session is loaded and **stop here**. Do not proceed to Phase 2.
- If an agent is active, note the **agent name** and **plugin** from the output and proceed.

## Phase 2: Teardown

### Step 1: Record Agent Identity

Before deleting state, capture the agent name and plugin from the Phase 1 result. You need these for the teardown announcement.

### Step 2: Delete State

Run:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state delete
```

### Step 3: Announce Teardown

Output the following block, replacing `{agent-name}` with the name captured in Step 1:

```
=== AGENT SESSION ENDED ===
The agent session for {agent-name} has been terminated.
Return to your default orchestrator persona. The behavioral instructions
between the previous AGENT SESSION ACTIVE markers are no longer in effect.
=== END SESSION TERMINATION ===
```

### Step 4: Confirm to User

Confirm to the user in a **neutral tone** that the agent session has ended and you have returned to default behavior. Do NOT use the agent's character, voice, or mannerisms in this confirmation -- speak as the plain orchestrator.

## Anti-Patterns

- Do NOT skip the state check in Phase 1. Always verify an agent is loaded before attempting teardown.
- Do NOT continue speaking in the agent's persona after the teardown block has been emitted.
- Do NOT delete state before reading the agent name. The name is needed for the announcement.
- Do NOT proceed to Phase 2 if Phase 1 shows no active agent.
