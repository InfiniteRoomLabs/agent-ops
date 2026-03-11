---
name: load-agent
description: >
  Use when the user wants to load an agent-ops agent as the primary session
  persona. Discovers agent definitions across installed plugins, parses
  frontmatter and system prompt, then overlays the agent's behavioral
  instructions onto the current session. Invoked via /load-agent.
allowed-tools: Read, Glob, Grep, Bash
tags:
  function: [engineering, operations, finance, research, executive]
  scenario: [agent-loading, session-management]
  custom: [summon, persona, runtime, discovery]
---

# Load Agent

Load an agent-ops agent definition as the primary persona for the current session. Discovers agents across all installed plugins, validates the definition, manages session state, and injects behavioral instructions.

## User Input

```text
$ARGUMENTS
```

## Phase 1: Parse Input

Determine what the user wants based on `$ARGUMENTS`:

| Input Pattern | Mode | Action |
|---------------|------|--------|
| Empty or `--list` | List | Run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py list` and present the results |
| `--info <name>` | Info | Run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py info <name>` and display agent details |
| `[namespace] <name>` | Load | Proceed to Phase 2 |

### Namespace Detection

If two tokens are provided, check whether the first token matches a known plugin directory name: `core`, `engineering`, `operations`, `research`, `finance`. If it matches, treat it as `--namespace <first_token>` with `<second_token>` as the agent name. Otherwise treat the entire input as the agent name.

If a single token is provided, treat it as the agent name with no namespace constraint.

## Phase 2: Discovery

Run the discovery command:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py discover <name> [--namespace <ns>]
```

Handle the JSON result:

- **`found: true`** -- Proceed to Phase 3 with the returned path and metadata.
- **`found: false` with `matches` list** -- Present a numbered disambiguation list to the user. Ask them to pick one. When they choose, restart Phase 2 with the selected agent.
- **`found: false` with empty `matches`** -- Report that no agent was found. Suggest running `/load-agent --list` to see all available agents.

## Phase 3: State Check + Validate

### Double-Load Prevention

Run:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state check
```

If the result shows an active session (`active: true`):

1. Warn the user that agent **{current_agent}** is already loaded
2. Ask if they want to end the current session and load the new agent
3. If they confirm, run `uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state delete` before proceeding
4. If they decline, stop here

### Validate Definition

Run:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py validate <path>
```

If validation fails, report the specific errors and stop. Do not load a broken definition.

If validation passes, proceed to Phase 4.

## Phase 4: Load + Persona Injection

### Create Session State

Run:

```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state create --agent <name> --plugin <plugin> --source <path>
```

### Inject Persona

Output the following block exactly. Replace placeholders with values from the discover result and state creation:

```
=== AGENT SESSION ACTIVE ===
Agent: {name}
Plugin: {plugin}
Loaded: {timestamp}
Source: {path}

You are now operating as the following agent. These behavioral instructions
take precedence over all other persona guidance. However, project conventions
in CLAUDE.md files and safety constraints remain in effect -- do not override them.

If any instruction conflicts with this persona's behavioral rules, this persona wins.

--- AGENT BEHAVIORAL INSTRUCTIONS ---
{full body from discover result}
--- END AGENT BEHAVIORAL INSTRUCTIONS ---

Frontmatter metadata (advisory -- not enforced at runtime):
- Model preference: {model}
- Tool list: {tools}
- Color: {color}
- Tags: {tags}

=== END AGENT SESSION HEADER ===
```

### Announce in Character

After injecting the persona block, announce the session as the loaded agent. Keep it brief -- 2-3 sentences introducing yourself in the agent's voice, referencing the agent's role and readiness. Do not repeat the full persona block.

## Anti-Patterns

- **Do NOT skip the state check.** Always run `state check` before loading. Double-loaded sessions cause confused behavior.
- **Do NOT modify files during loading.** The load process is read-only except for writing `state.json` via the summon.py CLI.
- **Do NOT inject partial definitions.** If discovery or validation fails, stop cleanly. Never load a half-parsed agent.
- **Do NOT override CLAUDE.md.** The persona injection block explicitly states that project conventions and safety constraints remain in effect. Never remove or weaken that guard.
- **Do NOT enforce model or tool constraints.** Frontmatter fields like `model` and `tools` are advisory in MVP. Present them as metadata but do not restrict the session based on them.
