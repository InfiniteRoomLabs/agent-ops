# Commit Guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-phase hook that warns on `git add` and blocks `git commit` when staged files match commonly gitignored patterns.

**Architecture:** New `scripts/commit_guard.py` with a hardcoded patterns list, a shared staged-file checker, and two Typer commands (`pre`/`post`) wired into the existing PreToolUse/PostToolUse Bash matchers in `hooks/hooks.json`.

**Tech Stack:** Python 3.12+, Typer, Pydantic, fnmatch, subprocess (git)

---

### Task 1: Create commit_guard.py with patterns list and matching logic

**Files:**
- Create: `scripts/commit_guard.py`

- [ ] **Step 1: Create the script with inline deps, imports, and Typer app**

Create `scripts/commit_guard.py`:

```python
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15"]
# ///
"""Guard against committing files that should be gitignored.

Usage:
  Human:  uv run commit_guard.py check
  Hook:   uv run commit_guard.py pre   (reads PreToolUse JSON from stdin)
          uv run commit_guard.py post  (reads PostToolUse JSON from stdin)
  List:   uv run commit_guard.py rules (print the active patterns table)
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass
from fnmatch import fnmatch
from pathlib import Path

import typer
from pydantic import BaseModel

app = typer.Typer(
    help="Guard against committing files that should be gitignored.",
    no_args_is_help=True,
)
```

- [ ] **Step 2: Add the IgnoredPattern dataclass and PATTERNS list**

Append to `scripts/commit_guard.py`, after the `app` definition:

```python
# ---------------------------------------------------------------------------
# Patterns table -- edit this to add ignored-path checks
# ---------------------------------------------------------------------------


@dataclass
class IgnoredPattern:
    """A single ignored-path pattern.

    pattern:    fnmatch glob. Trailing '/' means directory (match any path
                component). No trailing '/' means match the basename.
    ecosystem:  Human-readable label for output grouping.
    message:    Optional custom message. Falls back to generic if empty.
    """

    pattern: str
    ecosystem: str
    message: str = ""


PATTERNS: list[IgnoredPattern] = [
    # Python
    IgnoredPattern("__pycache__/", "Python"),
    IgnoredPattern(".venv/", "Python"),
    IgnoredPattern("venv/", "Python"),
    IgnoredPattern(".eggs/", "Python"),
    IgnoredPattern("*.egg-info/", "Python"),
    # Node
    IgnoredPattern("node_modules/", "Node"),
    IgnoredPattern(".npm/", "Node"),
    IgnoredPattern(".yarn/cache/", "Node"),
    # PHP
    IgnoredPattern("vendor/", "PHP"),
    # Ruby
    IgnoredPattern("vendor/bundle/", "Ruby"),
    # Rust
    IgnoredPattern("target/", "Rust"),
    # Java / JVM
    IgnoredPattern(".gradle/", "Java"),
    IgnoredPattern("build/", "Java"),
    # .NET
    IgnoredPattern("bin/", ".NET"),
    IgnoredPattern("obj/", ".NET"),
    IgnoredPattern("packages/", ".NET"),
    # General
    IgnoredPattern(".env", "General"),
    IgnoredPattern(".DS_Store", "General"),
    IgnoredPattern("Thumbs.db", "General"),
    IgnoredPattern("*.log", "General"),
]
```

- [ ] **Step 3: Add the Pydantic hook payload models**

Append to `scripts/commit_guard.py`:

```python
# ---------------------------------------------------------------------------
# Pydantic models for hook JSON payload
# ---------------------------------------------------------------------------


class ToolInput(BaseModel):
    command: str = ""


class HookPayload(BaseModel):
    tool_name: str = ""
    tool_input: ToolInput = ToolInput()
```

- [ ] **Step 4: Add matching logic and staged-file checker**

Append to `scripts/commit_guard.py`:

```python
# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------


def matches(file_path: str, pattern: str) -> bool:
    """Match a pattern against a staged file path.

    If the pattern ends with '/', strip the slash and check if any path
    component (directory segment) matches via fnmatch. This handles both
    plain names ('vendor/') and globs ('*.egg-info/').

    Otherwise, fnmatch against the basename.
    """
    if pattern.endswith("/"):
        dir_pattern = pattern.rstrip("/")
        parts = Path(file_path).parts
        return any(fnmatch(part, dir_pattern) for part in parts)
    return fnmatch(Path(file_path).name, pattern)


def find_violations(staged_files: list[str]) -> list[tuple[str, IgnoredPattern]]:
    """Return (file_path, matched_pattern) for every staged file that matches."""
    violations: list[tuple[str, IgnoredPattern]] = []
    for filepath in staged_files:
        for pat in PATTERNS:
            if matches(filepath, pat.pattern):
                violations.append((filepath, pat))
                break  # one match per file is enough
    return violations


def get_staged_files() -> list[str]:
    """Return the list of currently staged file paths."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]
```

- [ ] **Step 5: Verify the file parses cleanly**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run python -c "import ast; ast.parse(open('scripts/commit_guard.py').read()); print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add scripts/commit_guard.py
git commit -m "feat(commit-guard): add patterns list and matching logic"
```

---

### Task 2: Add the CLI commands (post, pre, check, rules)

**Files:**
- Modify: `scripts/commit_guard.py`

- [ ] **Step 1: Add the `post` command (PostToolUse warn-on-add)**

Append to `scripts/commit_guard.py`:

```python
# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def post() -> None:
    """PostToolUse hook: warn if staged files match ignored patterns after git add."""
    try:
        payload = HookPayload.model_validate_json(sys.stdin.read())
    except Exception:
        raise typer.Exit(0)

    if not re.search(r"git\s+add\b", payload.tool_input.command):
        raise typer.Exit(0)

    staged = get_staged_files()
    if not staged:
        raise typer.Exit(0)

    violations = find_violations(staged)
    for filepath, pat in violations:
        msg = pat.message or (
            f"'{filepath}' is a typically gitignored path ({pat.ecosystem}). "
            f"Consider adding '{pat.pattern}' to .gitignore and unstaging."
        )
        typer.echo(f"[commit-guard] WARNING: {msg}", err=True)

    raise typer.Exit(0)
```

- [ ] **Step 2: Add the `pre` command (PreToolUse block-on-commit)**

Append after the `post` command:

```python
@app.command()
def pre() -> None:
    """PreToolUse hook: block commit if staged files match ignored patterns."""
    payload = HookPayload.model_validate_json(sys.stdin.read())

    if not re.search(r"git\s+commit\b", payload.tool_input.command):
        raise typer.Exit(0)

    staged = get_staged_files()
    if not staged:
        raise typer.Exit(0)

    violations = find_violations(staged)
    if not violations:
        raise typer.Exit(0)

    lines = [f"  - {fp} ({pat.ecosystem}: {pat.pattern})" for fp, pat in violations]
    typer.echo(
        "BLOCKED: Commit includes paths that should be gitignored:\n"
        + "\n".join(lines)
        + "\n\nAdd these patterns to .gitignore and unstage the files before committing.",
        err=True,
    )
    raise typer.Exit(2)
```

- [ ] **Step 3: Add the `check` command (manual CLI)**

Append after the `pre` command:

```python
@app.command()
def check() -> None:
    """Check if any currently staged files match ignored patterns."""
    staged = get_staged_files()
    if not staged:
        typer.echo("No files staged.")
        raise typer.Exit(0)

    violations = find_violations(staged)
    if not violations:
        typer.echo(f"All {len(staged)} staged file(s) look clean.")
        raise typer.Exit(0)

    lines = [f"  - {fp} ({pat.ecosystem}: {pat.pattern})" for fp, pat in violations]
    typer.echo(
        "Staged files that should be gitignored:\n"
        + "\n".join(lines)
        + "\n\nAdd these patterns to .gitignore and unstage the files before committing.",
    )
    raise typer.Exit(1)
```

- [ ] **Step 4: Add the `rules` command and main block**

Append after the `check` command:

```python
@app.command()
def rules() -> None:
    """Print the active ignored-path patterns table."""
    current_eco = ""
    for pat in PATTERNS:
        if pat.ecosystem != current_eco:
            if current_eco:
                typer.echo("")
            typer.echo(f"  {pat.ecosystem}:")
            current_eco = pat.ecosystem
        note = f"  ({pat.message})" if pat.message else ""
        typer.echo(f"    {pat.pattern}{note}")


if __name__ == "__main__":
    app()
```

- [ ] **Step 5: Verify all four commands are registered**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run scripts/commit_guard.py --help`
Expected output should list: `check`, `post`, `pre`, `rules`

- [ ] **Step 6: Test the `rules` command**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run scripts/commit_guard.py rules`
Expected: Pattern table grouped by ecosystem, starting with `Python:` and listing `__pycache__/`, `.venv/`, etc.

- [ ] **Step 7: Test the `check` command with clean staging area**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run scripts/commit_guard.py check`
Expected: `No files staged.` with exit code 0.

- [ ] **Step 8: Commit**

```bash
git add scripts/commit_guard.py
git commit -m "feat(commit-guard): add post, pre, check, and rules commands"
```

---

### Task 3: Register hooks in hooks.json

**Files:**
- Modify: `hooks/hooks.json`

- [ ] **Step 1: Add `commit_guard.py pre` to the PreToolUse Bash matcher**

In `hooks/hooks.json`, add the following entry to the `PreToolUse` array's first object (the one with `"matcher": "Bash"`), in the `hooks` array after the `version_guard.py hook` entry and before the `pre-deploy-secrets-sync.sh` entry:

```json
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/commit_guard.py pre",
            "timeout": 10
          },
```

The PreToolUse Bash hooks array should now be (in order):
1. `changelog-guard.py hook`
2. `version_guard.py hook`
3. `commit_guard.py pre`
4. `pre-deploy-secrets-sync.sh`

- [ ] **Step 2: Add `commit_guard.py post` to the PostToolUse Bash matcher**

In `hooks/hooks.json`, add the following entry to the `PostToolUse` array's first object (the one with `"matcher": "Bash"`), in the `hooks` array after the `auto-tag.py hook` entry and before the `post-deploy-secrets-verify.sh` entry:

```json
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/commit_guard.py post",
            "timeout": 10
          },
```

The PostToolUse Bash hooks array should now be (in order):
1. `auto-tag.py hook`
2. `commit_guard.py post`
3. `post-deploy-secrets-verify.sh`

- [ ] **Step 3: Validate hooks.json is valid JSON**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && python -c "import json; json.load(open('hooks/hooks.json')); print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add hooks/hooks.json
git commit -m "feat(commit-guard): register pre and post hooks in hooks.json"
```

---

### Task 4: Manual integration test

**Files:** (none -- testing only)

- [ ] **Step 1: Test `pre` with a clean staging area (should pass)**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m \"test\""}}' | uv run scripts/commit_guard.py pre; echo "exit: $?"`
Expected: exit 0, no output.

- [ ] **Step 2: Test `pre` with non-commit command (should pass silently)**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && echo '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}' | uv run scripts/commit_guard.py pre; echo "exit: $?"`
Expected: exit 0, no output.

- [ ] **Step 3: Test `post` with non-add command (should pass silently)**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && echo '{"tool_name":"Bash","tool_input":{"command":"git status"}}' | uv run scripts/commit_guard.py post; echo "exit: $?"`
Expected: exit 0, no output.

- [ ] **Step 4: Test matching logic via `check` command with a dummy staged file**

Create a temporary file to stage, then check:

```bash
cd /tmp && git init commit-guard-test && cd commit-guard-test
mkdir -p node_modules __pycache__
echo "test" > node_modules/index.js
echo "test" > __pycache__/foo.cpython-312.pyc
echo "test" > clean_file.py
git add .
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
GIT_DIR=/tmp/commit-guard-test/.git GIT_WORK_TREE=/tmp/commit-guard-test uv run scripts/commit_guard.py check
```

Expected output should list `node_modules/index.js` and `__pycache__/foo.cpython-312.pyc` as violations, but not `clean_file.py`. Exit code 1.

- [ ] **Step 5: Clean up test repo**

```bash
rm -rf /tmp/commit-guard-test
```

- [ ] **Step 6: Test `pre` hook with the dummy staged file via pipe**

```bash
cd /tmp && git init commit-guard-test && cd commit-guard-test
mkdir -p vendor
echo "test" > vendor/autoload.php
git add .
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
echo '{"tool_name":"Bash","tool_input":{"command":"git commit -m \"test\""}}' | GIT_DIR=/tmp/commit-guard-test/.git GIT_WORK_TREE=/tmp/commit-guard-test uv run scripts/commit_guard.py pre 2>&1; echo "exit: $?"
```

Expected: `BLOCKED:` message listing `vendor/autoload.php (PHP: vendor/)`, exit 2.

- [ ] **Step 7: Test `post` hook with the dummy staged file via pipe**

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git add ."}}' | GIT_DIR=/tmp/commit-guard-test/.git GIT_WORK_TREE=/tmp/commit-guard-test uv run scripts/commit_guard.py post 2>&1; echo "exit: $?"
```

Expected: `[commit-guard] WARNING:` message about `vendor/autoload.php`, exit 0.

- [ ] **Step 8: Clean up test repo**

```bash
rm -rf /tmp/commit-guard-test
```
