# Commit Guard: Ignored-Path Detection Hook

## Purpose

Catch cases where an AI agent (or human) stages and commits files that should be gitignored -- `node_modules/`, `__pycache__/`, `vendor/`, etc. -- before they land in history. This guards against the agent forgetting to set up `.gitignore` properly.

## Approach

Two-phase detection using the git staging area (`git diff --cached --name-only`):

- **PostToolUse on `git add`**: Warn (stderr, exit 0) when newly staged files match known ignored patterns.
- **PreToolUse on `git commit`**: Hard-block (stderr, exit 2) if any staged files match known ignored patterns.

Both phases use the same staged-file check function. No command-string parsing for file paths -- the staging area is the single source of truth.

## Script

New file: `scripts/commit_guard.py`

- PEP 723 inline deps: `pydantic>=2`, `typer>=0.15`
- Typer CLI with four commands:
  - `post` -- PostToolUse hook entry point (warn after `git add`)
  - `pre` -- PreToolUse hook entry point (block before `git commit`)
  - `check` -- Manual CLI check for humans
  - `rules` -- Print the active patterns table

## Patterns Data Structure

```python
@dataclass
class IgnoredPattern:
    pattern: str        # fnmatch-style glob (e.g., "node_modules/", "*.pyc")
    ecosystem: str      # human-readable grouping for output (e.g., "Python", "Node")
    message: str = ""   # optional custom message, falls back to generic
```

### Matching Logic

- If the pattern ends with `/`, strip the trailing slash and check if any path component (directory segment) matches the resulting string via fnmatch. This handles both plain names (`vendor/`) and glob patterns (`*.egg-info/`).
- Otherwise, fnmatch against the basename of the staged file.
- `vendor/` matches `vendor/autoload.php` and `some/nested/vendor/file.js`.
- `*.egg-info/` matches `foo.egg-info/PKG-INFO`.
- `*.pyc` matches any `.pyc` file anywhere.

### Initial Pattern List

| Ecosystem | Patterns |
|-----------|----------|
| Python | `__pycache__/`, `.venv/`, `venv/`, `.eggs/`, `*.egg-info/` |
| Node | `node_modules/`, `.npm/`, `.yarn/cache/` |
| PHP | `vendor/` |
| Ruby | `vendor/bundle/` |
| Rust | `target/` |
| Java/JVM | `.gradle/`, `build/` |
| .NET | `bin/`, `obj/`, `packages/` |
| General | `.env`, `.DS_Store`, `Thumbs.db`, `*.log` |

## Messaging

### PostToolUse Warning (after `git add`)

```
[commit-guard] WARNING: 'node_modules/package.json' is a typically gitignored path (Node). Consider adding 'node_modules/' to .gitignore and unstaging.
```

Exit 0 -- never blocks staging.

### PreToolUse Block (before `git commit`)

```
BLOCKED: Commit includes paths that should be gitignored:
  - node_modules/package.json (Node: node_modules/)
  - __pycache__/foo.cpython-312.pyc (Python: __pycache__/)

Add these patterns to .gitignore and unstage the files before committing.
```

Exit 2 -- hard block.

## Hook Registration

Two entries added to `hooks/hooks.json`:

1. `commit_guard.py pre` added to the existing PreToolUse Bash matcher array (alongside changelog-guard and version-guard).
2. `commit_guard.py post` added to the existing PostToolUse Bash matcher array (alongside auto-tag).

```json
{
  "type": "command",
  "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/commit_guard.py pre",
  "timeout": 10
}
```

```json
{
  "type": "command",
  "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/commit_guard.py post",
  "timeout": 10
}
```

No new matchers needed.

## Files Changed

| File | Change |
|------|--------|
| `scripts/commit_guard.py` | New file |
| `hooks/hooks.json` | Add two hook entries to existing Bash matchers |
