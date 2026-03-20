# Hook Enforcement Architecture Design

**Date**: 2026-03-18
**Status**: Approved
**Relates to**: Idea 073 (CLAUDE.md Frontmatter Config Framework), Ideas 061-065 (Enforcement Cluster)

## Problem

The agent-ops plugin uses 3 of 13+ available Claude Code hook events. Ten new hook events shipped in Feb-Mar 2026 (InstructionsLoaded, PostCompact, ConfigChange, WorktreeCreate, WorktreeRemove, StopFailure, TeammateIdle, TaskCompleted, Elicitation, ElicitationResult). None are utilized. Meanwhile, 9 of 13 IRL repos have zero hooks at all.

Key gaps:

- Worktree agents run with zero git hook enforcement (worktrees don't inherit `.git/hooks/`)
- Nothing prevents mid-session disabling of hooks via settings.json edits
- CLAUDE.md encoding is only validated at commit time, not at load time
- PostCompact has no verification that critical context survived compaction
- No audit trail when sessions crash from API errors
- No quality gates on subagent output in NEXUS workflows
- No MCP elicitation logging or gating

Additionally, the frontmatter config pattern (proven in `accessibility-config.py`) is not generalized. Each hook that needs per-project config would reimplement the same CLAUDE.md hierarchy resolution.

## Solution

### 1. Shared Frontmatter Config Library (Idea 73)

Extract the CLAUDE.md hierarchy resolver into `scripts/frontmatter_config.py`. All hooks import it.

#### API

```python
from frontmatter_config import resolve_config, resolve_typed, resolve_frontmatter

# Returns merged dict for a namespace
config = resolve_config("enforcement")
# {"encoding": True, "tamper_detection": True, ...}

# Returns a typed Pydantic model
config = resolve_typed(EnforcementConfig, "enforcement")
# EnforcementConfig(encoding=True, tamper_detection=True, ...)

# Returns full merged frontmatter (all namespaces)
fm = resolve_frontmatter()
# {"enforcement": {...}, "accessibility": {...}, ...}
```

#### Hierarchy Resolution

1. `~/.claude/CLAUDE.md` (global)
2. Walk from CWD upward to home, collect all CLAUDE.md files
3. Merge in order: global -> outermost parent -> ... -> project (last wins)

Same algorithm as `accessibility-config.py`, extracted and tested independently.

#### Config Namespace Strategy

Flat top-level keys in YAML frontmatter. Each hook reads its own namespace. No plugin-scoped nesting.

```yaml
---
enforcement:
  encoding: true
accessibility:
  adhd:
    enabled: true
worktree:
  propagate_hooks: true
---
```

### 2. Hook Event Handlers

Seven new scripts covering all 10 new hook events. All follow the established PEP 723 pattern (inline dependencies, Typer CLI, Pydantic models, `uv run` compatible).

#### Tier 1: Protective (highest impact, ship first)

##### `instructions-guard.py` -- InstructionsLoaded

Validates CLAUDE.md and `.claude/rules/*.md` files as they load into context.

**Checks**:
- UTF-8 encoding validation (same rules as `validate_encoding.py` and git pre-commit hooks)
- `[PLACEHOLDER]` marker detection in scoped CLAUDE.md files
- Reports warnings to stderr

**Config namespace**: `enforcement`
```yaml
enforcement:
  encoding: true              # default: true
  placeholder_check: true     # default: true
```

**Exit behavior**: Always exit 0 (InstructionsLoaded is advisory, cannot block). Warnings go to stderr as JSON `systemMessage`.

**Stdin payload fields**: `file_path`, `memory_type`, `load_reason`, `globs`, `trigger_file_path`, `parent_file_path`. Note: the payload does NOT include file content. The script must read the file itself from `file_path` using `open(payload.file_path, "rb")` for encoding validation.

##### `postcompact-recovery.py` -- PostCompact

Verifies critical context survived compaction. Logs warnings if key context was lost.

**Important protocol constraint**: PostCompact stdout is NOT injected into conversation context. Only PreCompact can inject content. PostCompact is a side-effects-only event (audit, logging, verification).

**Behavior**:
1. Call `summon.py state check` -- if active persona, verify the `compact_summary` (from hook payload) still references the agent name. If not, emit a `systemMessage` warning.
2. Read `compaction.reinject` from frontmatter config -- check if each string appears in the compact summary. Log any missing strings as warnings.
3. Write verification results to audit trail at `~/.claude/projects/{slug}/memory/audit/compaction-checks.jsonl`

**Config namespace**: `compaction`
```yaml
compaction:
  reinject: []
  # Per-repo examples -- these strings are checked (not injected) after compaction:
  # reinject:
  #   - "ideas-cli.py"
  #   - "SECRET:credName"
```

**Exit behavior**: Always exit 0. Emits `{"systemMessage": "..."}` JSON to **stdout** if critical context was lost (this surfaces as a warning to the model). Note: stderr output is only visible in verbose/debug mode and would silently discard the warning. Always use stdout for structured responses.

**Coordination with PreCompact**: The existing `summon.py state reminder` on PreCompact injects context before compaction (belt). PostCompact verifies it survived (suspenders). If PostCompact detects loss, the `systemMessage` warning tells the model to re-read CLAUDE.md.

**Design change**: The `compaction.reinject` config key is used for verification (checking strings exist in compacted context), not injection. To actually inject strings before compaction, add them to the PreCompact hook's `summon.py state reminder` output.

##### `config-tamper-guard.py` -- ConfigChange

Detects and blocks unauthorized modifications to `.claude/settings.json`.

**Important protocol constraint**: The ConfigChange payload contains `session_id`, `transcript_path`, `cwd`, `hook_event_name`, `source`, and `file_path`. It does NOT contain before/after diffs. The script must maintain its own snapshot for comparison.

**Two-phase design**:
1. **Snapshot phase** (SessionStart): A companion SessionStart hook caches the current `.claude/settings.json` to `~/.claude/projects/{slug}/memory/audit/settings-snapshot.json`. This runs alongside the existing SessionStart hooks.
2. **Guard phase** (ConfigChange): Read the cached snapshot, read current file from `file_path` in payload, diff the two. Check if any `enforcement.protected_settings` keys were removed or weakened. Update the snapshot cache after validation.

**Additional constraint**: The `source` field in the payload indicates where the change originated. Changes from `policy_settings` source cannot be blocked (protocol constraint). The guard watches `project_settings`, `user_settings`, and `local_settings` sources. The `skills` source is excluded because skill files don't contain hook configuration -- they cannot disable enforcement via that vector. The `policy_settings` source is excluded because it's unblockable by protocol.

**Config namespace**: `enforcement`
```yaml
enforcement:
  protected_settings:
    - hooks                   # default: ["hooks", "permissions.deny"]
    - permissions.deny
```

**Exit behavior**: ConfigChange uses a JSON decision format on stdout, NOT exit 2:
- Allow: exit 0 with no output
- Block: exit 0 with `{"decision": "block", "reason": "Protected key 'hooks' was removed from settings.json"}` on stdout
- Error: exit 2 as fallback (generic deny, no structured reason)

The `reason` string is surfaced directly to the user/model. Always prefer the JSON decision format over exit 2 for actionable feedback.

**SessionStart addition**: Add `config-tamper-guard.py snapshot` to the SessionStart hooks array to cache the initial settings state.

##### `worktree-lifecycle.py` -- WorktreeCreate + WorktreeRemove

Manages enforcement propagation into and cleanup of git worktrees.

**Important protocol constraint**: WorktreeCreate REPLACES the default git worktree creation. The hook must perform the worktree creation itself and print the absolute path to the created worktree directory on stdout. If the hook is registered, Claude Code will NOT create the worktree -- the hook owns that entirely.

**On WorktreeCreate** (the hook IS the worktree creator):
1. Parse the hook payload for the requested worktree name/branch
2. Run `git worktree add` to create the worktree
3. Copy all executable files from main repo's `.git/hooks/` into the new worktree's `.git/hooks/`
4. Verify no `.env` files are present in the worktree
5. Log worktree creation to audit trail
6. Print the absolute path to the worktree directory on stdout (required by protocol)

**On WorktreeRemove**:
1. Log worktree removal to audit trail
2. Check for orphaned local branches associated with the worktree
3. Optionally clean orphaned branches (only if `clean_branches: true`)

**Important**: WorktreeRemove exit 2 is advisory-only and warnings only surface in debug mode. User-visible blocking of worktree removal is not supported by this event. If blocking is needed in the future, use a PreToolUse hook matching `git worktree remove`.

**Config namespace**: `worktree`
```yaml
worktree:
  propagate_hooks: true       # default: true
  check_uncommitted: true     # default: true (logged to audit, not user-visible)
  clean_branches: false       # default: false (destructive, opt-in only)
```

**Exit behavior**:
- WorktreeCreate: Exit 0 with worktree path on stdout = success. Exit non-zero = creation failure.
- WorktreeRemove: Exit 0 always (advisory, debug-only visibility).

**CLI interface**: `worktree-lifecycle.py create` and `worktree-lifecycle.py remove` subcommands matching Typer pattern.

#### Tier 2: Observability

##### `stop-failure-audit.py` -- StopFailure

Logs structured audit events when sessions crash from API errors.

**Important protocol constraint**: StopFailure exit code, stdout, and stderr are ALL entirely ignored. The hook can only perform side effects (file writes). This is acceptable for audit logging.

**Captured data** (from hook payload fields):
- Timestamp (ISO 8601, generated by script)
- `error` field: error type string (rate_limit, auth_failure, server_error, etc.)
- `error_details` field: additional error context
- Active agent persona (via `summon.py state check`)
- `session_id` field from payload
- `cwd` field from payload

**Output**: Appends JSONL to `~/.claude/projects/{slug}/memory/audit/stop-failures.jsonl`

**Config namespace**: `audit`
```yaml
audit:
  stop_failures: true         # default: true
  log_path: null              # default: null (uses standard audit path)
```

**Exit behavior**: Always exit 0. Audit logging is fire-and-forget.

#### Tier 3: Multi-Agent Quality Gates

##### `teammate-gate.py` -- TeammateIdle + TaskCompleted

Validates subagent output before the parent agent accepts it.

**Important protocol constraint**: TeammateIdle and TaskCompleted payloads contain `session_id`, `transcript_path`, `cwd`, `permission_mode`, `teammate_name`, `team_name`, and (for TaskCompleted) `task_id`, `task_subject`, `task_description`. They do NOT contain a list of changed files. The script must discover changes itself.

**On TaskCompleted**:
1. Run `git status --porcelain` in the teammate's `cwd` (from payload) to discover dirty files
2. Run encoding validation on modified markdown files
3. Check for `.env` file creation
4. Check for agent directory files (`.claude/`, `.codex/`, etc.)
5. Check for frontmatter violations in idea files (if in ideas repo)

**On TeammateIdle**:
- Same validation as TaskCompleted (a teammate going idle with dirty state is the same concern)

**Config namespace**: `enforcement`
```yaml
enforcement:
  teammate_validation: true   # default: true
  teammate_checks:            # default: ["encoding", "env_files", "agent_dirs"]
    - encoding
    - env_files
    - agent_dirs
```

**Exit behavior** (two distinct mechanisms):
- **Clean validation**: exit 0 with no output (teammate proceeds normally)
- **Fixable violations** (e.g., encoding issues): exit 2 with feedback message on stderr. This sends feedback to the teammate and re-runs it, giving it a chance to fix the problem.
- **Unrecoverable violations** (e.g., .env file creation, agent dir commits): exit 0 with `{"continue": false, "stopReason": "..."}` on stdout. This hard-stops the teammate immediately.

The distinction matters: exit 2 is "try again", `continue: false` is "you're done". Use exit 2 for things the teammate can fix, and hard-stop for security violations.

#### Tier 4: MCP Gating (Future-Ready)

##### `elicitation-gate.py` -- Elicitation + ElicitationResult

Logs and optionally gates MCP server elicitation requests.

**Important protocol constraint**: Elicitation blocking uses `hookSpecificOutput` on stdout with exit 0, NOT exit 2. Exit 2 causes a generic deny and falls back to user prompting. The correct blocking mechanism is:
```json
{"hookSpecificOutput": {"hookEventName": "Elicitation", "action": "decline"}}
```

**On Elicitation** (incoming request):
1. Log the request (MCP server name, request type, parameters) to audit trail
2. Check request against `block_patterns` regex list
3. If matched: exit 0 with `hookSpecificOutput.action = "decline"` on stdout
4. If not matched: exit 0 with no output (allow)

**On ElicitationResult** (outgoing response):
1. Log the response to audit trail
2. No blocking by default (response is already user-approved)

**Config namespace**: `mcp`
```yaml
mcp:
  audit_elicitations: true    # default: true
  block_patterns: []          # default: [] (no blocking)
```

**Exit behavior**: Both events always exit 0. Elicitation uses `hookSpecificOutput` for programmatic decline. ElicitationResult is audit-only.

### 3. Existing Hook Improvements

#### `accessibility-config.py` Refactor

Refactor from 174 lines to ~40 lines by importing `frontmatter_config.resolve_typed()`. Define `AdhdConfig` Pydantic model, call the library, output JSON. No behavior change.

**Key mismatch to resolve**: The existing `accessibility-config.py` uses `"momentum"` as the config key, but the Pydantic model field should match deployed YAML. Use `Field(alias="momentum_preservation")` with `model_config = ConfigDict(populate_by_name=True)` to accept both `momentum` (legacy) and `momentum_preservation` (canonical) in YAML frontmatter.

#### `summon.py` PreCompact + PostCompact Coordination

Keep PreCompact `state reminder` as-is. The new `postcompact-recovery.py` handles the PostCompact verification. No changes to summon.py itself.

#### Ideas Push-Review Conversion (Follow-Up)

Convert the ideas repo's prompt-type PreToolUse hook to a command hook calling `ideas-cli.py check all` before allowing `git push`. This moves review from model-interpreted to deterministic.

**Not part of this build** -- separate PR to the ideas repo. Noted here for tracking.

### 4. Updated `hooks.json`

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state clean --if-stale",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/accessibility-config.py",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/config-tamper-guard.py snapshot",
            "timeout": 5
          }
        ]
      }
    ],
    "InstructionsLoaded": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/instructions-guard.py hook",
            "timeout": 10
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state reminder",
            "timeout": 10
          }
        ]
      }
    ],
    "PostCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/postcompact-recovery.py hook",
            "timeout": 10
          }
        ]
      }
    ],
    "ConfigChange": [
      {
        "matcher": "project_settings|user_settings|local_settings",
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/config-tamper-guard.py hook",
            "timeout": 10
          }
        ]
      }
    ],
    "WorktreeCreate": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/worktree-lifecycle.py create",
            "timeout": 15
          }
        ]
      }
    ],
    "WorktreeRemove": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/worktree-lifecycle.py remove",
            "timeout": 10
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/changelog-guard.py hook",
            "timeout": 10
          },
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/version_guard.py hook",
            "timeout": 15
          }
        ]
      }
    ],
    "StopFailure": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/stop-failure-audit.py hook",
            "timeout": 10
          }
        ]
      }
    ],
    "TeammateIdle": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/teammate-gate.py idle",
            "timeout": 15
          }
        ]
      }
    ],
    "TaskCompleted": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/teammate-gate.py completed",
            "timeout": 15
          }
        ]
      }
    ],
    "Elicitation": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/elicitation-gate.py request",
            "timeout": 10
          }
        ]
      }
    ],
    "ElicitationResult": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/elicitation-gate.py result",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

### 5. Frontmatter Config Schema (Complete)

Full schema with all defaults. Repos only need to declare overrides.

```yaml
---
# Enforcement -- instructions-guard, config-tamper-guard, teammate-gate
enforcement:
  encoding: true                    # Validate UTF-8 in CLAUDE.md on load
  placeholder_check: true           # Detect [PLACEHOLDER] markers
  protected_settings:               # Settings keys that can't be removed mid-session
    - hooks
    - permissions.deny
  teammate_validation: true         # Validate subagent output
  teammate_checks:                  # Checks to run on subagent files
    - encoding
    - env_files
    - agent_dirs
  push_validation: false            # CLI-based push review (opt-in per-repo)

# Compaction -- postcompact-recovery
compaction:
  reinject: []                      # Strings re-injected after compaction

# Worktree -- worktree-lifecycle
worktree:
  propagate_hooks: true             # Copy .git/hooks into worktrees
  check_uncommitted: true           # Warn on uncommitted work at removal
  clean_branches: false             # Delete orphaned branches (destructive, opt-in)

# Audit -- stop-failure-audit
audit:
  stop_failures: true               # Log API failure events
  log_path: null                    # null = default audit directory

# MCP -- elicitation-gate
mcp:
  audit_elicitations: true          # Log MCP elicitation events
  block_patterns: []                # Regex patterns to deny

# Accessibility -- accessibility-config (existing, unchanged)
accessibility:
  adhd:
    enabled: false
    micro_chunking: true
    reduced_decisions: true
    response_brevity: true
    momentum: true                # Note: existing deployed key is "momentum", not "momentum_preservation"
    progress_dopamine: true
    context_anchoring: true
    anti_rabbit_hole: true
    time_awareness: true
    sensory_friendly: true
    max_options: 2
    max_prose_lines: 4
    break_interval_minutes: 30
---
```

### 6. Build Order

| # | File | Event | Depends On |
|---|------|-------|------------|
| 1 | `frontmatter_config.py` | -- | Nothing (foundation) |
| 2 | `accessibility-config.py` | SessionStart | #1 (refactor to use library) |
| 3 | `instructions-guard.py` | InstructionsLoaded | #1 |
| 4 | `postcompact-recovery.py` | PostCompact | #1 |
| 5 | `config-tamper-guard.py` | ConfigChange | #1 |
| 6 | `worktree-lifecycle.py` | WorktreeCreate + WorktreeRemove | #1 |
| 7 | `stop-failure-audit.py` | StopFailure | #1 |
| 8 | `teammate-gate.py` | TeammateIdle + TaskCompleted | #1 |
| 9 | `elicitation-gate.py` | Elicitation + ElicitationResult | #1 |
| 10 | `hooks.json` | -- | #2-#9 (all scripts exist) |

### 7. Testing Strategy

Each script gets a corresponding test file in `tests/`:
- `test_frontmatter_config.py` -- hierarchy resolution, merge semantics, typed models
- `test_instructions_guard.py` -- encoding detection, placeholder detection
- `test_postcompact_recovery.py` -- reinject output, summon coordination
- `test_config_tamper_guard.py` -- protected key detection, before/after diff
- `test_worktree_lifecycle.py` -- hook copy, env detection, branch cleanup
- `test_stop_failure_audit.py` -- JSONL output format, audit fields
- `test_teammate_gate.py` -- encoding checks, env file detection, continue/stop output
- `test_elicitation_gate.py` -- audit logging, pattern blocking

All tests use the existing conftest.py fixtures pattern. No OS keyring or real git repos -- mock filesystem and subprocess calls.

### 8. Follow-Up Work (Not This Build)

- **Ideas repo**: Convert push-review prompt hook to command hook calling `ideas-cli.py`
- **Per-repo CLAUDE.md**: Add `compaction.reinject` strings to ideas, infra, CCSM repos
- **Plugin version**: Bump to 1.3.0 (new features, no breaking changes)
