# Hook Enforcement Architecture Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a shared frontmatter config library and 7 new hook scripts covering all 10 new Claude Code hook events, plus refactor the existing accessibility-config.py and update hooks.json.

**Architecture:** PEP 723 scripts with inline dependencies, Typer CLI + Pydantic models, `uv run` compatible. Shared library (`frontmatter_config.py`) extracts CLAUDE.md hierarchy resolution. All hooks read per-project config via the library. TDD throughout.

**IMPORTANT -- Local import pattern:** All hook scripts import `frontmatter_config` which is a local file, not a PyPI package. PEP 723 inline deps only cover PyPI packages. Every script that imports `frontmatter_config` MUST add this before the import:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
```
This ensures `uv run scripts/foo.py` can find `scripts/frontmatter_config.py`.

**IMPORTANT -- Audit slug format:** Claude Code project directories use the full path with `/` replaced by `-`, prefixed with `-` (e.g., `-home-deathnerd-projects-agent-ops`). When computing audit paths, derive the slug as:
```python
slug = cwd.replace("/", "-")  # e.g., "/home/user/project" -> "-home-user-project"
audit_dir = Path.home() / ".claude" / "projects" / slug / "memory" / "audit"
```
Do NOT use `Path(cwd).name` (that gives just the last component).

**Tech Stack:** Python 3.12+, Pydantic v2, Typer 0.15+, PyYAML 6+, uv (PEP 723 inline deps)

**Spec:** `docs/plans/2026-03-18-hook-enforcement-architecture-design.md`

---

## File Map

| # | File | Purpose | Creates/Modifies |
|---|------|---------|-----------------|
| 1 | `scripts/frontmatter_config.py` | Shared CLAUDE.md frontmatter config library | Create |
| 2 | `tests/test_frontmatter_config.py` | Tests for the shared library | Create |
| 3 | `scripts/accessibility-config.py` | Refactor to use shared library | Modify |
| 4 | `scripts/instructions-guard.py` | InstructionsLoaded hook handler | Create |
| 5 | `tests/test_instructions_guard.py` | Tests for instructions-guard | Create |
| 6 | `scripts/postcompact-recovery.py` | PostCompact hook handler | Create |
| 7 | `tests/test_postcompact_recovery.py` | Tests for postcompact-recovery | Create |
| 8 | `scripts/config-tamper-guard.py` | ConfigChange hook handler + SessionStart snapshot | Create |
| 9 | `tests/test_config_tamper_guard.py` | Tests for config-tamper-guard | Create |
| 10 | `scripts/worktree-lifecycle.py` | WorktreeCreate + WorktreeRemove hook handler | Create |
| 11 | `tests/test_worktree_lifecycle.py` | Tests for worktree-lifecycle | Create |
| 12 | `scripts/stop-failure-audit.py` | StopFailure hook handler | Create |
| 13 | `tests/test_stop_failure_audit.py` | Tests for stop-failure-audit | Create |
| 14 | `scripts/teammate-gate.py` | TeammateIdle + TaskCompleted hook handler | Create |
| 15 | `tests/test_teammate_gate.py` | Tests for teammate-gate | Create |
| 16 | `scripts/elicitation-gate.py` | Elicitation + ElicitationResult hook handler | Create |
| 17 | `tests/test_elicitation_gate.py` | Tests for elicitation-gate | Create |
| 18 | `hooks/hooks.json` | Updated hook registry with all 13 events | Modify |
| 19 | `CHANGELOG.md` | Document new hooks | Modify |
| 20 | `.claude-plugin/plugin.json` | Version bump to 1.3.0 | Modify |

---

## Chunk 1: Shared Frontmatter Config Library

### Task 1: `frontmatter_config.py` -- Core library

**Files:**
- Create: `scripts/frontmatter_config.py`
- Create: `tests/test_frontmatter_config.py`

The library extracts the CLAUDE.md hierarchy resolution pattern from `accessibility-config.py` into a reusable module. Three public functions: `resolve_config()`, `resolve_typed()`, `resolve_frontmatter()`.

Reference the existing implementation at `scripts/accessibility-config.py:59-97` for the hierarchy walk algorithm.

- [ ] **Step 1: Write failing tests for `parse_frontmatter()`**

```python
# tests/test_frontmatter_config.py
"""Tests for the shared frontmatter config library."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_parse_frontmatter_valid():
    from frontmatter_config import parse_frontmatter

    content = "---\nfoo: bar\nbaz: 42\n---\n\n# Hello"
    result = parse_frontmatter(content)
    assert result == {"foo": "bar", "baz": 42}


def test_parse_frontmatter_no_frontmatter():
    from frontmatter_config import parse_frontmatter

    result = parse_frontmatter("# Just markdown\nNo frontmatter here.")
    assert result is None


def test_parse_frontmatter_invalid_yaml():
    from frontmatter_config import parse_frontmatter

    content = "---\n: invalid: yaml: [unterminated\n---\n"
    result = parse_frontmatter(content)
    assert result is None


def test_parse_frontmatter_nested():
    from frontmatter_config import parse_frontmatter

    content = "---\nenforcement:\n  encoding: true\n  placeholder_check: false\n---\n"
    result = parse_frontmatter(content)
    assert result == {"enforcement": {"encoding": True, "placeholder_check": False}}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_frontmatter_config.py -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError`

- [ ] **Step 3: Write `parse_frontmatter()` and `find_claude_md_files()`**

```python
# scripts/frontmatter_config.py
# /// script
# dependencies = ["pyyaml>=6", "pydantic>=2"]
# ///
"""Shared CLAUDE.md frontmatter config library.

Resolves YAML frontmatter from CLAUDE.md files using a hierarchy walk:
global (~/.claude/CLAUDE.md) -> parent directories -> project (CWD).
Later files override earlier ones ("last wins").

Usage:
    from frontmatter_config import resolve_config, resolve_typed, resolve_frontmatter
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from typing import TypeVar

import yaml
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None
    try:
        result = yaml.safe_load(match.group(1))
        return result if isinstance(result, dict) else None
    except yaml.YAMLError:
        return None


def find_claude_md_files(cwd: Path | None = None) -> list[Path]:
    """Find CLAUDE.md files: global first, then project hierarchy (most general first)."""
    files: list[Path] = []
    resolved_cwd = (cwd or Path.cwd()).resolve()
    home = Path.home().resolve()

    # Global user config
    global_md = home / ".claude" / "CLAUDE.md"
    if global_md.is_file():
        files.append(global_md)

    # Walk up from CWD collecting CLAUDE.md files (child -> parent order)
    project_files: list[Path] = []
    seen: set[Path] = set()
    current = resolved_cwd

    while current != current.parent and current != home:
        candidate = current / "CLAUDE.md"
        resolved = candidate.resolve()
        if candidate.is_file() and resolved not in seen:
            seen.add(resolved)
            project_files.append(candidate)
        current = current.parent

    # Reverse so most general (parent) comes first, most specific (CWD) last
    files.extend(reversed(project_files))
    return files
```

- [ ] **Step 4: Run tests to verify `parse_frontmatter` tests pass**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_frontmatter_config.py -v -k parse`
Expected: 4 PASS

- [ ] **Step 5: Write failing tests for `resolve_frontmatter()` and `resolve_config()`**

```python
# Append to tests/test_frontmatter_config.py

def test_resolve_frontmatter_merges_hierarchy(tmp_path: Path):
    from frontmatter_config import resolve_frontmatter

    # Create parent CLAUDE.md
    parent = tmp_path / "parent"
    parent.mkdir()
    (parent / "CLAUDE.md").write_text(
        "---\nenforcement:\n  encoding: true\n  placeholder_check: true\n---\n"
    )

    # Create child CLAUDE.md that overrides one key
    child = parent / "child"
    child.mkdir()
    (child / "CLAUDE.md").write_text(
        "---\nenforcement:\n  placeholder_check: false\nworktree:\n  propagate_hooks: true\n---\n"
    )

    result = resolve_frontmatter(cwd=child, home_override=tmp_path)
    assert result["enforcement"]["encoding"] is True  # inherited from parent
    assert result["enforcement"]["placeholder_check"] is False  # overridden by child
    assert result["worktree"]["propagate_hooks"] is True  # only in child


def test_resolve_config_returns_namespace(tmp_path: Path):
    from frontmatter_config import resolve_config

    project = tmp_path / "project"
    project.mkdir()
    (project / "CLAUDE.md").write_text(
        "---\nenforcement:\n  encoding: true\naudit:\n  stop_failures: false\n---\n"
    )

    result = resolve_config("enforcement", cwd=project, home_override=tmp_path)
    assert result == {"encoding": True}


def test_resolve_config_missing_namespace(tmp_path: Path):
    from frontmatter_config import resolve_config

    project = tmp_path / "project"
    project.mkdir()
    (project / "CLAUDE.md").write_text("---\nfoo: bar\n---\n")

    result = resolve_config("enforcement", cwd=project, home_override=tmp_path)
    assert result == {}
```

- [ ] **Step 6: Write `_deep_merge()`, `resolve_frontmatter()`, and `resolve_config()`**

```python
# Add to scripts/frontmatter_config.py after find_claude_md_files()

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Override values win."""
    result = copy.deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def resolve_frontmatter(
    cwd: Path | None = None,
    home_override: Path | None = None,
) -> dict:
    """Resolve merged frontmatter from the CLAUDE.md hierarchy.

    Args:
        cwd: Working directory to resolve from. Defaults to Path.cwd().
        home_override: Override Path.home() for testing. If set, the global
            CLAUDE.md is looked up at home_override/.claude/CLAUDE.md and
            the walk stops at home_override instead of the real home.
    """
    resolved_cwd = (cwd or Path.cwd()).resolve()
    home = (home_override or Path.home()).resolve()

    files: list[Path] = []

    # Global
    global_md = home / ".claude" / "CLAUDE.md"
    if global_md.is_file():
        files.append(global_md)

    # Walk up
    project_files: list[Path] = []
    seen: set[Path] = set()
    current = resolved_cwd

    while current != current.parent and current != home:
        candidate = current / "CLAUDE.md"
        resolved = candidate.resolve()
        if candidate.is_file() and resolved not in seen:
            seen.add(resolved)
            project_files.append(candidate)
        current = current.parent

    files.extend(reversed(project_files))

    # Merge
    merged: dict = {}
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        fm = parse_frontmatter(content)
        if fm:
            merged = _deep_merge(merged, fm)

    return merged


def resolve_config(
    namespace: str,
    cwd: Path | None = None,
    home_override: Path | None = None,
) -> dict:
    """Resolve a single namespace from merged frontmatter.

    Returns the dict under the given top-level key, or {} if not found.
    """
    fm = resolve_frontmatter(cwd=cwd, home_override=home_override)
    value = fm.get(namespace, {})
    return value if isinstance(value, dict) else {}
```

- [ ] **Step 7: Run all frontmatter tests**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_frontmatter_config.py -v`
Expected: 7 PASS

- [ ] **Step 8: Write failing test for `resolve_typed()`**

```python
# Append to tests/test_frontmatter_config.py

from pydantic import BaseModel, Field


class EnforcementConfig(BaseModel):
    encoding: bool = True
    placeholder_check: bool = True
    protected_settings: list[str] = Field(default_factory=lambda: ["hooks", "permissions.deny"])


def test_resolve_typed_returns_model(tmp_path: Path):
    from frontmatter_config import resolve_typed

    project = tmp_path / "project"
    project.mkdir()
    (project / "CLAUDE.md").write_text(
        "---\nenforcement:\n  encoding: false\n---\n"
    )

    result = resolve_typed(EnforcementConfig, "enforcement", cwd=project, home_override=tmp_path)
    assert isinstance(result, EnforcementConfig)
    assert result.encoding is False
    assert result.placeholder_check is True  # default


def test_resolve_typed_missing_namespace_returns_defaults(tmp_path: Path):
    from frontmatter_config import resolve_typed

    project = tmp_path / "project"
    project.mkdir()
    (project / "CLAUDE.md").write_text("---\nfoo: bar\n---\n")

    result = resolve_typed(EnforcementConfig, "enforcement", cwd=project, home_override=tmp_path)
    assert result.encoding is True
    assert result.placeholder_check is True
    assert result.protected_settings == ["hooks", "permissions.deny"]
```

- [ ] **Step 9: Write `resolve_typed()`**

```python
# Add to scripts/frontmatter_config.py after resolve_config()

def resolve_typed(
    model: type[T],
    namespace: str,
    cwd: Path | None = None,
    home_override: Path | None = None,
) -> T:
    """Resolve a namespace and validate it against a Pydantic model.

    Missing keys use model defaults. Extra keys are ignored.
    """
    raw = resolve_config(namespace, cwd=cwd, home_override=home_override)
    return model.model_validate(raw)
```

- [ ] **Step 10: Run all tests**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_frontmatter_config.py -v`
Expected: 9 PASS

- [ ] **Step 11: Write edge case tests**

```python
# Append to tests/test_frontmatter_config.py

def test_deep_merge_nested_dicts():
    from frontmatter_config import _deep_merge

    base = {"a": {"b": 1, "c": 2}, "d": 3}
    override = {"a": {"c": 99, "e": 4}}
    result = _deep_merge(base, override)
    assert result == {"a": {"b": 1, "c": 99, "e": 4}, "d": 3}


def test_deep_merge_override_replaces_non_dict():
    from frontmatter_config import _deep_merge

    base = {"a": [1, 2, 3]}
    override = {"a": [4, 5]}
    result = _deep_merge(base, override)
    assert result == {"a": [4, 5]}


def test_resolve_frontmatter_no_claude_md(tmp_path: Path):
    from frontmatter_config import resolve_frontmatter

    empty = tmp_path / "empty"
    empty.mkdir()
    result = resolve_frontmatter(cwd=empty, home_override=tmp_path)
    assert result == {}


def test_resolve_frontmatter_skips_unreadable(tmp_path: Path):
    from frontmatter_config import resolve_frontmatter

    project = tmp_path / "project"
    project.mkdir()
    bad_file = project / "CLAUDE.md"
    bad_file.write_bytes(b"---\nkey: \xff\xfe bad bytes\n---\n")

    result = resolve_frontmatter(cwd=project, home_override=tmp_path)
    assert result == {}
```

- [ ] **Step 12: Run full test suite**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_frontmatter_config.py -v`
Expected: 13 PASS

- [ ] **Step 13: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add scripts/frontmatter_config.py tests/test_frontmatter_config.py
git commit -m "feat: add shared frontmatter config library (idea 73)"
```

---

### Task 2: Refactor `accessibility-config.py` to use shared library

**Files:**
- Modify: `scripts/accessibility-config.py`
- Reference: `scripts/frontmatter_config.py`

This refactor replaces the inline hierarchy walker with a call to the shared library. No behavior change.

- [ ] **Step 1: Verify existing behavior (baseline)**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run scripts/accessibility-config.py`
Expected: JSON output with ADHD config (since global CLAUDE.md has `accessibility.adhd.enabled: true`)

Save the output for comparison after refactor.

- [ ] **Step 2: Rewrite `accessibility-config.py` using the shared library**

Replace the entire file with:

```python
# /// script
# dependencies = ["pyyaml>=6", "pydantic>=2"]
# ///
"""
Accessibility config detector for Claude Code.

Reads CLAUDE.md files (global and project-level), parses YAML frontmatter,
and outputs accessibility configuration if found. Used by the SessionStart
hook to auto-activate ADHD accessibility mode.

Usage:
    uv run accessibility-config.py [--check]

    --check: Exit 0 if config found and enabled, 1 if not (no output)
    (default): Output structured config as JSON if found, nothing if not
"""

import json
import sys

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_config

BEHAVIOR_LABELS = {
    "micro_chunking": "Micro-Chunking",
    "reduced_decisions": "Reduced Decision Points",
    "response_brevity": "Response Brevity",
    "momentum": "Momentum Preservation",
    "progress_dopamine": "Progress Dopamine",
    "context_anchoring": "Context Anchoring",
    "anti_rabbit_hole": "Anti-Rabbit-Hole Guardrails",
    "time_awareness": "Time Awareness",
    "sensory_friendly": "Sensory-Friendly Formatting",
}

DEFAULT_ADHD_CONFIG = {
    "enabled": False,
    "micro_chunking": True,
    "reduced_decisions": True,
    "max_options": 2,
    "response_brevity": True,
    "max_prose_lines": 4,
    "momentum": True,
    "progress_dopamine": True,
    "context_anchoring": True,
    "anti_rabbit_hole": True,
    "time_awareness": True,
    "break_interval_minutes": 30,
    "sensory_friendly": True,
}


def main():
    check_only = "--check" in sys.argv

    # Use the shared library to resolve the accessibility.adhd namespace.
    # resolve_config("accessibility") returns the top-level accessibility dict,
    # then we extract the "adhd" sub-key.
    accessibility = resolve_config("accessibility")
    adhd_raw = accessibility.get("adhd")

    if not isinstance(adhd_raw, dict):
        if check_only:
            sys.exit(1)
        return

    config = {**DEFAULT_ADHD_CONFIG, **adhd_raw}

    if not config.get("enabled", False):
        if check_only:
            sys.exit(1)
        return

    if check_only:
        sys.exit(0)

    enabled = []
    disabled = []
    for key, label in BEHAVIOR_LABELS.items():
        if config.get(key, True):
            enabled.append(label)
        else:
            disabled.append(label)

    output = {
        "accessibility_mode": "adhd",
        "auto_activated": True,
        "enabled_behaviors": enabled,
        "disabled_behaviors": disabled,
        "settings": {
            "max_options": config.get("max_options", 2),
            "max_prose_lines": config.get("max_prose_lines", 4),
            "break_interval_minutes": config.get("break_interval_minutes", 30),
        },
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Verify behavior is identical**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run scripts/accessibility-config.py`
Expected: Identical JSON output to Step 1 baseline.

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run scripts/accessibility-config.py --check && echo "enabled" || echo "disabled"`
Expected: `enabled`

- [ ] **Step 4: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add scripts/accessibility-config.py
git commit -m "refactor: accessibility-config uses shared frontmatter library"
```

---

## Chunk 2: Tier 1 Hooks -- InstructionsLoaded + PostCompact

### Task 3: `instructions-guard.py` -- InstructionsLoaded

**Files:**
- Create: `scripts/instructions-guard.py`
- Create: `tests/test_instructions_guard.py`

Validates UTF-8 encoding and detects `[PLACEHOLDER]` markers when CLAUDE.md/rules files load. Advisory only (exit 0 always). Warnings go to stderr.

The hook payload does NOT include file content. The script reads from `file_path` in the payload.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_instructions_guard.py
"""Tests for the InstructionsLoaded hook handler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_clean_file_no_warnings(tmp_path: Path, capsys):
    from instructions_guard import validate_file

    f = tmp_path / "CLAUDE.md"
    f.write_text("# Clean file\nAll ASCII here.\n", encoding="utf-8")
    warnings = validate_file(f, encoding_check=True, placeholder_check=True)
    assert warnings == []


def test_detects_smart_quotes(tmp_path: Path):
    from instructions_guard import validate_file

    f = tmp_path / "CLAUDE.md"
    # LEFT DOUBLE QUOTATION MARK (U+201C)
    f.write_bytes(b"# Test\nSome \xe2\x80\x9csmart quotes\xe2\x80\x9d here.\n")
    warnings = validate_file(f, encoding_check=True, placeholder_check=False)
    assert len(warnings) == 1
    assert "encoding" in warnings[0].lower() or "smart quote" in warnings[0].lower()


def test_detects_placeholder_markers(tmp_path: Path):
    from instructions_guard import validate_file

    f = tmp_path / "CLAUDE.md"
    f.write_text("# API Layer\n[PLACEHOLDER] Add your API docs here.\n")
    warnings = validate_file(f, encoding_check=False, placeholder_check=True)
    assert len(warnings) == 1
    assert "PLACEHOLDER" in warnings[0]


def test_no_placeholder_check_when_disabled(tmp_path: Path):
    from instructions_guard import validate_file

    f = tmp_path / "CLAUDE.md"
    f.write_text("# API Layer\n[PLACEHOLDER] Add your API docs here.\n")
    warnings = validate_file(f, encoding_check=False, placeholder_check=False)
    assert warnings == []


def test_missing_file_no_crash(tmp_path: Path):
    from instructions_guard import validate_file

    f = tmp_path / "nonexistent.md"
    warnings = validate_file(f, encoding_check=True, placeholder_check=True)
    assert warnings == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_instructions_guard.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `instructions-guard.py`**

```python
# scripts/instructions-guard.py
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""InstructionsLoaded hook: validates CLAUDE.md and rules files as they load.

Checks UTF-8 encoding and detects [PLACEHOLDER] markers. Advisory only.

Usage:
    Hook:  uv run instructions-guard.py hook  (reads JSON from stdin)
    CLI:   uv run instructions-guard.py check <file>
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Annotated, Optional

import typer
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed

app = typer.Typer(
    help="Validate CLAUDE.md and rules files on load.",
    no_args_is_help=True,
)

# Characters that indicate encoding problems (Windows-1252 artifacts in UTF-8)
PROBLEMATIC_CHARS = {
    "\u201c": "LEFT DOUBLE QUOTATION MARK",
    "\u201d": "RIGHT DOUBLE QUOTATION MARK",
    "\u2018": "LEFT SINGLE QUOTATION MARK",
    "\u2019": "RIGHT SINGLE QUOTATION MARK",
    "\u2013": "EN DASH",
    "\u2014": "EM DASH",
    "\u2026": "HORIZONTAL ELLIPSIS",
    "\u2022": "BULLET",
    "\u00a0": "NO-BREAK SPACE",
    "\u2192": "RIGHTWARDS ARROW",
}

PLACEHOLDER_RE = re.compile(r"\[PLACEHOLDER\]", re.IGNORECASE)


class EnforcementConfig(BaseModel):
    encoding: bool = True
    placeholder_check: bool = True


class HookPayload(BaseModel):
    file_path: str = ""
    memory_type: str = ""
    load_reason: str = ""


def validate_file(
    path: Path,
    *,
    encoding_check: bool = True,
    placeholder_check: bool = True,
) -> list[str]:
    """Validate a file for encoding issues and placeholder markers.

    Returns a list of warning strings. Empty list = clean.
    """
    warnings: list[str] = []

    if not path.is_file():
        return warnings

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        warnings.append(f"Cannot read {path}: {e}")
        return warnings

    if encoding_check:
        found_chars: list[str] = []
        for char, name in PROBLEMATIC_CHARS.items():
            if char in content:
                found_chars.append(name)
        if found_chars:
            warnings.append(
                f"Encoding issues in {path.name}: found {', '.join(found_chars)}. "
                f"Replace with ASCII equivalents."
            )

    if placeholder_check:
        matches = PLACEHOLDER_RE.findall(content)
        if matches:
            warnings.append(
                f"Found {len(matches)} [PLACEHOLDER] marker(s) in {path.name}. "
                f"Replace with actual content before use."
            )

    return warnings


@app.command()
def check(
    file_path: Annotated[str, typer.Argument(help="File to validate")],
) -> None:
    """Validate a single file for encoding and placeholder issues."""
    path = Path(file_path)
    warnings = validate_file(path, encoding_check=True, placeholder_check=True)
    for w in warnings:
        typer.echo(f"WARNING: {w}", err=True)
    raise typer.Exit(1 if warnings else 0)


@app.command()
def hook() -> None:
    """InstructionsLoaded hook entry point. Reads JSON from stdin."""
    payload = HookPayload.model_validate_json(sys.stdin.read())

    if not payload.file_path:
        raise typer.Exit(0)

    config = resolve_typed(EnforcementConfig, "enforcement")
    warnings = validate_file(
        Path(payload.file_path),
        encoding_check=config.encoding,
        placeholder_check=config.placeholder_check,
    )

    if warnings:
        # systemMessage goes to STDOUT (stderr is debug-only, would be discarded)
        output = {"systemMessage": " | ".join(warnings)}
        print(json.dumps(output))

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_instructions_guard.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add scripts/instructions-guard.py tests/test_instructions_guard.py
git commit -m "feat: add instructions-guard for InstructionsLoaded hook"
```

---

### Task 4: `postcompact-recovery.py` -- PostCompact

**Files:**
- Create: `scripts/postcompact-recovery.py`
- Create: `tests/test_postcompact_recovery.py`

Verifies critical context survived compaction. Outputs `systemMessage` to **stdout** if context was lost. Writes audit JSONL. PostCompact stdout is NOT injected into context -- it surfaces as a model-visible warning.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_postcompact_recovery.py
"""Tests for the PostCompact hook handler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_no_reinject_strings_no_warning(capsys):
    from postcompact_recovery import check_compaction

    result = check_compaction(
        compact_summary="Session about coding tasks.",
        reinject_strings=[],
        agent_name=None,
    )
    assert result["warnings"] == []


def test_missing_reinject_string_produces_warning():
    from postcompact_recovery import check_compaction

    result = check_compaction(
        compact_summary="Session about general work.",
        reinject_strings=["ideas-cli.py", "SECRET:credName"],
        agent_name=None,
    )
    assert len(result["warnings"]) == 2
    assert any("ideas-cli.py" in w for w in result["warnings"])


def test_present_reinject_string_no_warning():
    from postcompact_recovery import check_compaction

    result = check_compaction(
        compact_summary="User must use ideas-cli.py for all ID allocation.",
        reinject_strings=["ideas-cli.py"],
        agent_name=None,
    )
    assert result["warnings"] == []


def test_agent_name_missing_from_summary():
    from postcompact_recovery import check_compaction

    result = check_compaction(
        compact_summary="Session about building features.",
        reinject_strings=[],
        agent_name="backend-architect",
    )
    assert len(result["warnings"]) == 1
    assert "backend-architect" in result["warnings"][0]


def test_agent_name_present_in_summary():
    from postcompact_recovery import check_compaction

    result = check_compaction(
        compact_summary="Operating as backend-architect for infrastructure work.",
        reinject_strings=[],
        agent_name="backend-architect",
    )
    assert result["warnings"] == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_postcompact_recovery.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `postcompact-recovery.py`**

```python
# scripts/postcompact-recovery.py
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""PostCompact hook: verifies critical context survived compaction.

Checks for agent persona and reinject strings in the compact summary.
Outputs systemMessage to stdout if context was lost.

Usage:
    Hook:  uv run postcompact-recovery.py hook  (reads JSON from stdin)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed

app = typer.Typer(help="PostCompact verification hook.", no_args_is_help=True)


class CompactionConfig(BaseModel):
    reinject: list[str] = []


class HookPayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    compact_summary: str = ""


def check_compaction(
    *,
    compact_summary: str,
    reinject_strings: list[str],
    agent_name: str | None,
) -> dict:
    """Check if critical context survived compaction.

    Returns dict with "warnings" list.
    """
    warnings: list[str] = []

    # Check agent persona
    if agent_name and agent_name.lower() not in compact_summary.lower():
        warnings.append(
            f"Agent persona '{agent_name}' not found in compacted context. "
            f"The model may have lost awareness of the active agent."
        )

    # Check reinject strings
    for s in reinject_strings:
        if s.lower() not in compact_summary.lower():
            warnings.append(
                f"Critical context '{s}' not found in compacted context. "
                f"This rule may have been lost during compaction."
            )

    return {"warnings": warnings}


def _get_active_agent() -> str | None:
    """Check summon state for active agent name."""
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if not plugin_root:
        return None
    try:
        result = subprocess.run(
            ["uv", "run", f"{plugin_root}/scripts/summon.py", "state", "check"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if data.get("active"):
                return data.get("agent", {}).get("active_agent")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


def _write_audit(cwd: str, session_id: str, warnings: list[str]) -> None:
    """Append compaction check results to audit trail."""
    # Derive project slug from cwd using Claude Code's path format
    slug = cwd.replace("/", "-") if cwd else "-unknown"
    audit_dir = Path.home() / ".claude" / "projects" / slug / "memory" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "compaction_check",
        "session_id": session_id,
        "warnings": warnings,
        "warnings_count": len(warnings),
    }

    audit_file = audit_dir / "compaction-checks.jsonl"
    with audit_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


@app.command()
def hook() -> None:
    """PostCompact hook entry point. Reads JSON from stdin."""
    payload = HookPayload.model_validate_json(sys.stdin.read())

    config = resolve_typed(CompactionConfig, "compaction")
    agent_name = _get_active_agent()

    result = check_compaction(
        compact_summary=payload.compact_summary,
        reinject_strings=config.reinject,
        agent_name=agent_name,
    )

    # Write audit trail
    _write_audit(payload.cwd, payload.session_id, result["warnings"])

    # Output systemMessage to stdout if warnings found
    if result["warnings"]:
        msg = (
            "POST-COMPACTION WARNING: The following critical context may have been lost "
            "during compaction. Re-read CLAUDE.md if needed:\n"
            + "\n".join(f"  - {w}" for w in result["warnings"])
        )
        print(json.dumps({"systemMessage": msg}))

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_postcompact_recovery.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add scripts/postcompact-recovery.py tests/test_postcompact_recovery.py
git commit -m "feat: add postcompact-recovery for PostCompact hook"
```

---

## Chunk 3: Tier 1 Hooks -- ConfigChange + Worktree

### Task 5: `config-tamper-guard.py` -- ConfigChange + SessionStart snapshot

**Files:**
- Create: `scripts/config-tamper-guard.py`
- Create: `tests/test_config_tamper_guard.py`

Two-phase design: `snapshot` subcommand caches settings at SessionStart; `hook` subcommand diffs against cache on ConfigChange. Blocking uses JSON decision format on stdout: `{"decision": "block", "reason": "..."}`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_config_tamper_guard.py
"""Tests for the ConfigChange hook handler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_snapshot_creates_cache(tmp_path: Path):
    from config_tamper_guard import snapshot_settings

    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({"hooks": {"PreToolUse": []}, "other": "value"}))
    cache_dir = tmp_path / "cache"

    snapshot_settings(settings_path=settings, cache_dir=cache_dir)

    cache_file = cache_dir / "settings-snapshot.json"
    assert cache_file.is_file()
    cached = json.loads(cache_file.read_text())
    assert cached["hooks"]["PreToolUse"] == []


def test_detect_removed_protected_key(tmp_path: Path):
    from config_tamper_guard import detect_tamper

    before = {"hooks": {"PreToolUse": [{"type": "command"}]}, "other": "value"}
    after = {"other": "value"}  # hooks key removed

    result = detect_tamper(before, after, protected_keys=["hooks"])
    assert result["tampered"] is True
    assert any("hooks" in r for r in result["reasons"])


def test_no_tamper_when_keys_present(tmp_path: Path):
    from config_tamper_guard import detect_tamper

    before = {"hooks": {"PreToolUse": []}, "permissions": {"deny": ["rm"]}}
    after = {"hooks": {"PreToolUse": [], "PostToolUse": []}, "permissions": {"deny": ["rm"]}}

    result = detect_tamper(before, after, protected_keys=["hooks", "permissions.deny"])
    assert result["tampered"] is False


def test_detect_weakened_deny_list(tmp_path: Path):
    from config_tamper_guard import detect_tamper

    before = {"permissions": {"deny": ["rm", "sudo"]}}
    after = {"permissions": {"deny": ["rm"]}}  # sudo removed

    result = detect_tamper(before, after, protected_keys=["permissions.deny"])
    assert result["tampered"] is True
    assert any("permissions.deny" in r for r in result["reasons"])


def test_no_tamper_on_unprotected_changes():
    from config_tamper_guard import detect_tamper

    before = {"hooks": {}, "theme": "dark"}
    after = {"hooks": {}, "theme": "light"}

    result = detect_tamper(before, after, protected_keys=["hooks"])
    assert result["tampered"] is False
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_config_tamper_guard.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `config-tamper-guard.py`**

```python
# scripts/config-tamper-guard.py
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""ConfigChange hook: detects unauthorized settings modifications.

Two-phase design:
  snapshot: Caches settings.json at SessionStart
  hook:     Diffs against cache on ConfigChange, blocks if protected keys removed

Usage:
    SessionStart: uv run config-tamper-guard.py snapshot
    ConfigChange: uv run config-tamper-guard.py hook  (reads JSON from stdin)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import typer
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed

app = typer.Typer(help="Settings tamper detection guard.", no_args_is_help=True)


class EnforcementConfig(BaseModel):
    protected_settings: list[str] = Field(
        default_factory=lambda: ["hooks", "permissions.deny"]
    )


class HookPayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    source: str = ""
    file_path: str = ""


def _get_cache_dir() -> Path:
    """Get the cache directory for settings snapshots."""
    cwd_slug = str(Path.cwd()).replace("/", "-")
    cache = Path.home() / ".claude" / "projects" / cwd_slug / "memory" / "audit"
    cache.mkdir(parents=True, exist_ok=True)
    return cache


def _resolve_dotted(data: dict, dotted_key: str) -> Any:
    """Resolve a dotted key path in a nested dict. Returns None if not found."""
    keys = dotted_key.split(".")
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def snapshot_settings(
    *,
    settings_path: Path | None = None,
    cache_dir: Path | None = None,
) -> None:
    """Cache the current settings.json for later comparison."""
    if settings_path is None:
        settings_path = Path.cwd() / ".claude" / "settings.json"
    if cache_dir is None:
        cache_dir = _get_cache_dir()

    cache_dir.mkdir(parents=True, exist_ok=True)

    if not settings_path.is_file():
        return

    content = settings_path.read_text(encoding="utf-8")
    cache_file = cache_dir / "settings-snapshot.json"
    cache_file.write_text(content, encoding="utf-8")


def detect_tamper(
    before: dict,
    after: dict,
    protected_keys: list[str],
) -> dict:
    """Compare before/after settings and check for protected key removal.

    Returns dict with "tampered" bool and "reasons" list.
    """
    reasons: list[str] = []

    for key in protected_keys:
        before_val = _resolve_dotted(before, key)
        after_val = _resolve_dotted(after, key)

        # Key was present before but removed or set to None
        if before_val is not None and after_val is None:
            reasons.append(f"Protected key '{key}' was removed from settings.")
            continue

        # For list values: check if items were removed (weakened)
        if isinstance(before_val, list) and isinstance(after_val, list):
            removed = set(str(v) for v in before_val) - set(str(v) for v in after_val)
            if removed:
                reasons.append(
                    f"Protected key '{key}' was weakened: "
                    f"removed {', '.join(sorted(removed))}."
                )
                continue

        # For dict values: check if sub-keys were removed
        if isinstance(before_val, dict) and isinstance(after_val, dict):
            removed_keys = set(before_val.keys()) - set(after_val.keys())
            if removed_keys:
                reasons.append(
                    f"Protected key '{key}' lost sub-keys: "
                    f"{', '.join(sorted(removed_keys))}."
                )

    return {"tampered": len(reasons) > 0, "reasons": reasons}


@app.command()
def snapshot() -> None:
    """Cache current settings.json (run at SessionStart)."""
    snapshot_settings()
    raise typer.Exit(0)


@app.command()
def hook() -> None:
    """ConfigChange hook entry point. Reads JSON from stdin."""
    payload = HookPayload.model_validate_json(sys.stdin.read())

    config = resolve_typed(EnforcementConfig, "enforcement")
    cache_dir = _get_cache_dir()
    cache_file = cache_dir / "settings-snapshot.json"

    # Load cached snapshot
    if not cache_file.is_file():
        # No snapshot = can't compare. Allow and snapshot current state.
        if payload.file_path and Path(payload.file_path).is_file():
            snapshot_settings(settings_path=Path(payload.file_path), cache_dir=cache_dir)
        raise typer.Exit(0)

    try:
        before = json.loads(cache_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise typer.Exit(0)

    # Load current settings
    current_path = Path(payload.file_path) if payload.file_path else None
    if not current_path or not current_path.is_file():
        raise typer.Exit(0)

    try:
        after = json.loads(current_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        raise typer.Exit(0)

    result = detect_tamper(before, after, config.protected_settings)

    # Update snapshot to current state (for next change detection)
    snapshot_settings(settings_path=current_path, cache_dir=cache_dir)

    if result["tampered"]:
        reason = " ".join(result["reasons"])
        decision = {"decision": "block", "reason": reason}
        print(json.dumps(decision))

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_config_tamper_guard.py -v`
Expected: 5 PASS

- [ ] **Step 5: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add scripts/config-tamper-guard.py tests/test_config_tamper_guard.py
git commit -m "feat: add config-tamper-guard for ConfigChange hook"
```

---

### Task 6: `worktree-lifecycle.py` -- WorktreeCreate + WorktreeRemove

**Files:**
- Create: `scripts/worktree-lifecycle.py`
- Create: `tests/test_worktree_lifecycle.py`

WorktreeCreate REPLACES default git worktree creation. The hook must call `git worktree add` itself and print the absolute path on stdout. WorktreeRemove is advisory/audit-only.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_worktree_lifecycle.py
"""Tests for worktree lifecycle hook handler."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture()
def git_repo(tmp_path: Path):
    """Create a temporary git repo with hooks."""
    prev = os.getcwd()
    os.chdir(tmp_path)
    subprocess.run(["git", "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
    (tmp_path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], check=True, capture_output=True)

    # Create a sample git hook
    hooks_dir = tmp_path / ".git" / "hooks"
    hook_file = hooks_dir / "pre-commit"
    hook_file.write_text("#!/bin/sh\nexit 0\n")
    hook_file.chmod(0o755)

    yield tmp_path
    os.chdir(prev)


def test_copy_hooks_to_worktree(git_repo: Path):
    from worktree_lifecycle import copy_git_hooks

    # Create a worktree manually for testing the copy function
    wt_path = git_repo.parent / "test-wt"
    subprocess.run(
        ["git", "worktree", "add", str(wt_path), "-b", "test-branch"],
        check=True, capture_output=True,
    )

    copied = copy_git_hooks(main_repo=git_repo, worktree=wt_path)

    # Verify the hook was actually copied
    assert "pre-commit" in copied

    # Resolve the worktree's real git dir and verify the file exists there
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True, text=True, cwd=str(wt_path),
    )
    wt_git_dir = Path(result.stdout.strip())
    if not wt_git_dir.is_absolute():
        wt_git_dir = wt_path / wt_git_dir
    assert (wt_git_dir / "hooks" / "pre-commit").is_file()


def test_check_env_files_finds_env(tmp_path: Path):
    from worktree_lifecycle import check_env_files

    (tmp_path / ".env").write_text("SECRET=bad\n")
    warnings = check_env_files(tmp_path)
    assert len(warnings) == 1
    assert ".env" in warnings[0]


def test_check_env_files_clean(tmp_path: Path):
    from worktree_lifecycle import check_env_files

    warnings = check_env_files(tmp_path)
    assert warnings == []
```

- [ ] **Step 2: Run tests to verify failure**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_worktree_lifecycle.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Implement `worktree-lifecycle.py`**

```python
# scripts/worktree-lifecycle.py
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""WorktreeCreate + WorktreeRemove hook handler.

WorktreeCreate REPLACES default git worktree creation. This hook:
1. Creates the worktree via git worktree add
2. Copies git hooks from main repo
3. Checks for .env files
4. Prints the absolute worktree path on stdout (required by protocol)

WorktreeRemove is advisory-only (debug visibility only).

Usage:
    Hook:  uv run worktree-lifecycle.py create  (reads JSON from stdin)
    Hook:  uv run worktree-lifecycle.py remove   (reads JSON from stdin)
"""

from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed

app = typer.Typer(help="Worktree lifecycle management.", no_args_is_help=True)


class WorktreeConfig(BaseModel):
    propagate_hooks: bool = True
    check_uncommitted: bool = True
    clean_branches: bool = False


class CreatePayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    worktree_name: str = ""
    branch: str = ""


class RemovePayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    worktree_path: str = ""


def _get_git_root() -> Path | None:
    """Get the root of the current git repository."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except (subprocess.TimeoutExpired, OSError):
        pass
    return None


def copy_git_hooks(*, main_repo: Path, worktree: Path) -> list[str]:
    """Copy executable git hooks from main repo into the worktree's git dir.

    In a worktree, .git is a FILE (not a directory) pointing to the main
    repo's .git/worktrees/<name>/. We resolve the real git dir via
    `git rev-parse --git-dir` and copy hooks there.

    Returns list of copied hook names.
    """
    copied: list[str] = []
    source_hooks = main_repo / ".git" / "hooks"

    if not source_hooks.is_dir():
        return copied

    # Resolve the worktree's actual git dir
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, text=True, cwd=str(worktree), timeout=5,
        )
        if result.returncode != 0:
            return copied
        wt_git_dir = Path(result.stdout.strip())
        if not wt_git_dir.is_absolute():
            wt_git_dir = worktree / wt_git_dir
    except (subprocess.TimeoutExpired, OSError):
        return copied

    dest_hooks = wt_git_dir / "hooks"
    dest_hooks.mkdir(parents=True, exist_ok=True)

    for hook_file in source_hooks.iterdir():
        if hook_file.is_file() and not hook_file.name.endswith(".sample"):
            if hook_file.stat().st_mode & stat.S_IXUSR:
                dest = dest_hooks / hook_file.name
                shutil.copy2(hook_file, dest)
                dest.chmod(hook_file.stat().st_mode)
                copied.append(hook_file.name)

    return copied


def check_env_files(worktree: Path) -> list[str]:
    """Check for .env files in the worktree root."""
    warnings: list[str] = []
    for f in worktree.iterdir():
        if f.is_file() and (f.name == ".env" or f.name.startswith(".env.")):
            if f.name != ".env.example" and f.name != ".envrc":
                warnings.append(f"Found {f.name} in worktree. This may contain secrets.")
    return warnings


def _write_audit(event: str, data: dict) -> None:
    """Write audit entry for worktree events."""
    cwd = data.get("cwd", "")
    slug = cwd.replace("/", "-") if cwd else "-unknown"
    audit_dir = Path.home() / ".claude" / "projects" / slug / "memory" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        **data,
    }

    with (audit_dir / "worktree-events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


@app.command()
def create() -> None:
    """WorktreeCreate hook. Creates worktree, copies hooks, prints path."""
    payload = CreatePayload.model_validate_json(sys.stdin.read())
    config = resolve_typed(WorktreeConfig, "worktree")

    git_root = _get_git_root()
    if not git_root:
        typer.echo("ERROR: Not in a git repository.", err=True)
        raise typer.Exit(1)

    # Determine worktree path
    wt_name = payload.worktree_name or f"worktree-{payload.session_id[:8]}"
    wt_path = git_root.parent / wt_name

    # Create the worktree
    cmd = ["git", "worktree", "add", str(wt_path)]
    if payload.branch:
        cmd.extend(["-b", payload.branch])

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        typer.echo(f"ERROR: git worktree add failed: {result.stderr}", err=True)
        raise typer.Exit(1)

    # Copy hooks if configured
    if config.propagate_hooks:
        copied = copy_git_hooks(main_repo=git_root, worktree=wt_path)
        if copied:
            typer.echo(
                f"Propagated {len(copied)} git hook(s) to worktree: {', '.join(copied)}",
                err=True,
            )

    # Check for .env files
    env_warnings = check_env_files(wt_path)
    for w in env_warnings:
        typer.echo(f"WARNING: {w}", err=True)

    # Audit
    _write_audit("worktree_created", {
        "cwd": payload.cwd,
        "worktree_path": str(wt_path),
        "branch": payload.branch,
        "hooks_copied": config.propagate_hooks,
    })

    # Print the absolute path on stdout (required by protocol)
    print(str(wt_path.resolve()))
    raise typer.Exit(0)


@app.command()
def remove() -> None:
    """WorktreeRemove hook. Audit-only (debug visibility)."""
    payload = RemovePayload.model_validate_json(sys.stdin.read())
    config = resolve_typed(WorktreeConfig, "worktree")

    wt_path = Path(payload.worktree_path) if payload.worktree_path else None

    # Check for uncommitted work
    if config.check_uncommitted and wt_path and wt_path.is_dir():
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=str(wt_path),
        )
        if result.stdout.strip():
            typer.echo(
                f"WARNING: Worktree has uncommitted changes:\n{result.stdout}",
                err=True,
            )

    # Audit
    _write_audit("worktree_removed", {
        "cwd": payload.cwd,
        "worktree_path": payload.worktree_path,
    })

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_worktree_lifecycle.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add scripts/worktree-lifecycle.py tests/test_worktree_lifecycle.py
git commit -m "feat: add worktree-lifecycle for WorktreeCreate/Remove hooks"
```

---

## Chunk 4: Tier 2-4 Hooks + hooks.json

### Task 7: `stop-failure-audit.py` -- StopFailure

**Files:**
- Create: `scripts/stop-failure-audit.py`
- Create: `tests/test_stop_failure_audit.py`

Fire-and-forget audit logging. All output channels are ignored by protocol. Only side effect is JSONL file write.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_stop_failure_audit.py
"""Tests for the StopFailure audit hook."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_write_audit_entry(tmp_path: Path):
    from stop_failure_audit import write_failure_audit

    write_failure_audit(
        audit_dir=tmp_path,
        error="rate_limit",
        error_details="429 Too Many Requests",
        session_id="sess-123",
        cwd="/home/user/project",
        agent_name="backend-architect",
    )

    audit_file = tmp_path / "stop-failures.jsonl"
    assert audit_file.is_file()
    entry = json.loads(audit_file.read_text().strip())
    assert entry["error"] == "rate_limit"
    assert entry["error_details"] == "429 Too Many Requests"
    assert entry["session_id"] == "sess-123"
    assert entry["agent_name"] == "backend-architect"
    assert "timestamp" in entry


def test_write_audit_appends(tmp_path: Path):
    from stop_failure_audit import write_failure_audit

    write_failure_audit(audit_dir=tmp_path, error="e1", error_details="", session_id="s1", cwd="/p", agent_name=None)
    write_failure_audit(audit_dir=tmp_path, error="e2", error_details="", session_id="s2", cwd="/p", agent_name=None)

    lines = (tmp_path / "stop-failures.jsonl").read_text().strip().split("\n")
    assert len(lines) == 2


def test_write_audit_no_agent(tmp_path: Path):
    from stop_failure_audit import write_failure_audit

    write_failure_audit(audit_dir=tmp_path, error="auth", error_details="", session_id="s", cwd="/p", agent_name=None)
    entry = json.loads((tmp_path / "stop-failures.jsonl").read_text().strip())
    assert entry["agent_name"] is None
```

- [ ] **Step 2: Implement and run tests**

```python
# scripts/stop-failure-audit.py
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""StopFailure hook: logs structured audit events when sessions crash.

All output channels (exit, stdout, stderr) are ignored by protocol.
Only side effect is JSONL file write.

Usage:
    Hook:  uv run stop-failure-audit.py hook  (reads JSON from stdin)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed

app = typer.Typer(help="StopFailure audit logger.", no_args_is_help=True)


class AuditConfig(BaseModel):
    stop_failures: bool = True
    log_path: str | None = None


class HookPayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    error: str = ""
    error_details: str = ""


def _get_active_agent() -> str | None:
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if not plugin_root:
        return None
    try:
        result = subprocess.run(
            ["uv", "run", f"{plugin_root}/scripts/summon.py", "state", "check"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if data.get("active"):
                return data.get("agent", {}).get("active_agent")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


def write_failure_audit(
    *,
    audit_dir: Path,
    error: str,
    error_details: str,
    session_id: str,
    cwd: str,
    agent_name: str | None,
) -> None:
    """Write a single failure audit entry to JSONL."""
    audit_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": "stop_failure",
        "error": error,
        "error_details": error_details,
        "session_id": session_id,
        "cwd": cwd,
        "agent_name": agent_name,
    }
    with (audit_dir / "stop-failures.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


@app.command()
def hook() -> None:
    """StopFailure hook entry point. Reads JSON from stdin."""
    payload = HookPayload.model_validate_json(sys.stdin.read())
    config = resolve_typed(AuditConfig, "audit")

    if not config.stop_failures:
        raise typer.Exit(0)

    if config.log_path:
        audit_dir = Path(config.log_path)
    else:
        slug = payload.cwd.replace("/", "-") if payload.cwd else "-unknown"
        audit_dir = Path.home() / ".claude" / "projects" / slug / "memory" / "audit"

    agent_name = _get_active_agent()

    write_failure_audit(
        audit_dir=audit_dir,
        error=payload.error,
        error_details=payload.error_details,
        session_id=payload.session_id,
        cwd=payload.cwd,
        agent_name=agent_name,
    )

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
```

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_stop_failure_audit.py -v`
Expected: 3 PASS

- [ ] **Step 3: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add scripts/stop-failure-audit.py tests/test_stop_failure_audit.py
git commit -m "feat: add stop-failure-audit for StopFailure hook"
```

---

### Task 8: `teammate-gate.py` -- TeammateIdle + TaskCompleted

**Files:**
- Create: `scripts/teammate-gate.py`
- Create: `tests/test_teammate_gate.py`

Discovers changed files via `git status --porcelain` (not from payload). Two exit mechanisms: exit 2 for fixable violations (retry), `continue: false` for security violations (hard stop).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_teammate_gate.py
"""Tests for TeammateIdle/TaskCompleted hook handler."""

from __future__ import annotations

from pathlib import Path

import pytest


def test_encoding_check_finds_smart_quotes(tmp_path: Path):
    from teammate_gate import check_encoding

    f = tmp_path / "test.md"
    f.write_bytes(b"Some \xe2\x80\x9csmart\xe2\x80\x9d text\n")
    violations = check_encoding([f])
    assert len(violations) == 1


def test_encoding_check_clean_file(tmp_path: Path):
    from teammate_gate import check_encoding

    f = tmp_path / "test.md"
    f.write_text("Clean ASCII text.\n")
    violations = check_encoding([f])
    assert violations == []


def test_env_file_check_finds_env(tmp_path: Path):
    from teammate_gate import check_env_files

    (tmp_path / ".env").write_text("SECRET=bad\n")
    violations = check_env_files([tmp_path / ".env"])
    assert len(violations) == 1


def test_agent_dir_check_finds_claude_dir(tmp_path: Path):
    from teammate_gate import check_agent_dirs

    claude_file = tmp_path / ".claude" / "settings.json"
    violations = check_agent_dirs([claude_file])
    assert len(violations) == 1


def test_classify_violations():
    from teammate_gate import classify_violations

    violations = [
        {"type": "encoding", "message": "bad chars", "severity": "fixable"},
        {"type": "env_file", "message": ".env created", "severity": "security"},
    ]
    fixable, security = classify_violations(violations)
    assert len(fixable) == 1
    assert len(security) == 1
```

- [ ] **Step 2: Implement and run tests**

```python
# scripts/teammate-gate.py
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""TeammateIdle + TaskCompleted hook: validates subagent output.

Discovers changed files via git status. Two exit mechanisms:
  - exit 2 + stderr message: fixable violations (teammate retries)
  - exit 0 + {"continue": false}: security violations (hard stop)

Usage:
    Hook:  uv run teammate-gate.py idle       (reads JSON from stdin)
    Hook:  uv run teammate-gate.py completed   (reads JSON from stdin)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import typer
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed

app = typer.Typer(help="Teammate output validation gate.", no_args_is_help=True)

PROBLEMATIC_CHARS = {
    "\u201c", "\u201d", "\u2018", "\u2019",
    "\u2013", "\u2014", "\u2026", "\u2022",
    "\u00a0", "\u2192",
}

AGENT_DIRS = {
    ".claude", ".codex", ".gemini", ".cursor", ".qwen",
    ".opencode", ".windsurf", ".kilocode", ".augment", ".roo",
    ".amazonq",
}


class EnforcementConfig(BaseModel):
    teammate_validation: bool = True
    teammate_checks: list[str] = Field(
        default_factory=lambda: ["encoding", "env_files", "agent_dirs"]
    )


class HookPayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    teammate_name: str = ""
    team_name: str = ""
    task_id: str = ""
    task_subject: str = ""


def _get_dirty_files(cwd: str) -> list[Path]:
    """Get list of modified/new files from git status."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, cwd=cwd, timeout=10,
        )
        files: list[Path] = []
        for line in result.stdout.strip().splitlines():
            if len(line) > 3:
                filepath = line[3:].strip()
                # Handle renames (old -> new)
                if " -> " in filepath:
                    filepath = filepath.split(" -> ")[1]
                files.append(Path(cwd) / filepath)
        return files
    except (subprocess.TimeoutExpired, OSError):
        return []


def check_encoding(files: list[Path]) -> list[dict]:
    """Check markdown files for problematic characters."""
    violations: list[dict] = []
    for f in files:
        if not f.suffix.lower() in (".md", ".markdown"):
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found = [c for c in PROBLEMATIC_CHARS if c in content]
        if found:
            violations.append({
                "type": "encoding",
                "file": str(f),
                "message": f"Encoding issues in {f.name}: {len(found)} problematic character(s).",
                "severity": "fixable",
            })
    return violations


def check_env_files(files: list[Path]) -> list[dict]:
    """Check for .env file creation."""
    violations: list[dict] = []
    for f in files:
        if f.name == ".env" or (f.name.startswith(".env.") and f.name not in (".env.example", ".envrc")):
            violations.append({
                "type": "env_file",
                "file": str(f),
                "message": f"Created {f.name} which may contain secrets.",
                "severity": "security",
            })
    return violations


def check_agent_dirs(files: list[Path]) -> list[dict]:
    """Check for agent directory file modifications."""
    violations: list[dict] = []
    for f in files:
        for agent_dir in AGENT_DIRS:
            if f"/{agent_dir}/" in str(f) or str(f).startswith(f"{agent_dir}/"):
                violations.append({
                    "type": "agent_dir",
                    "file": str(f),
                    "message": f"Modified file in agent directory {agent_dir}/.",
                    "severity": "security",
                })
                break
    return violations


def classify_violations(
    violations: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split violations into fixable and security categories."""
    fixable = [v for v in violations if v["severity"] == "fixable"]
    security = [v for v in violations if v["severity"] == "security"]
    return fixable, security


def _validate(payload: HookPayload) -> None:
    """Run validation checks on teammate output."""
    config = resolve_typed(EnforcementConfig, "enforcement")

    if not config.teammate_validation:
        raise typer.Exit(0)

    files = _get_dirty_files(payload.cwd)
    if not files:
        raise typer.Exit(0)

    all_violations: list[dict] = []

    if "encoding" in config.teammate_checks:
        all_violations.extend(check_encoding(files))
    if "env_files" in config.teammate_checks:
        all_violations.extend(check_env_files(files))
    if "agent_dirs" in config.teammate_checks:
        all_violations.extend(check_agent_dirs(files))

    if not all_violations:
        raise typer.Exit(0)

    fixable, security = classify_violations(all_violations)

    # Security violations = hard stop
    if security:
        reasons = [v["message"] for v in security]
        output = {
            "continue": False,
            "stopReason": "Security violation: " + "; ".join(reasons),
        }
        print(json.dumps(output))
        raise typer.Exit(0)

    # Fixable violations = retry
    if fixable:
        messages = [v["message"] for v in fixable]
        typer.echo(
            "Teammate output has fixable issues:\n"
            + "\n".join(f"  - {m}" for m in messages)
            + "\nPlease fix these before completing.",
            err=True,
        )
        raise typer.Exit(2)

    raise typer.Exit(0)


@app.command()
def idle() -> None:
    """TeammateIdle hook entry point."""
    payload = HookPayload.model_validate_json(sys.stdin.read())
    _validate(payload)


@app.command()
def completed() -> None:
    """TaskCompleted hook entry point."""
    payload = HookPayload.model_validate_json(sys.stdin.read())
    _validate(payload)


if __name__ == "__main__":
    app()
```

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_teammate_gate.py -v`
Expected: 5 PASS

- [ ] **Step 3: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add scripts/teammate-gate.py tests/test_teammate_gate.py
git commit -m "feat: add teammate-gate for TeammateIdle/TaskCompleted hooks"
```

---

### Task 9: `elicitation-gate.py` -- Elicitation + ElicitationResult

**Files:**
- Create: `scripts/elicitation-gate.py`
- Create: `tests/test_elicitation_gate.py`

Audit logging + optional blocking via `hookSpecificOutput` with `action: "decline"`. Both events always exit 0.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_elicitation_gate.py
"""Tests for Elicitation/ElicitationResult hook handler."""

from __future__ import annotations

import json
from pathlib import Path

import pytest


def test_no_block_patterns_allows(capsys):
    from elicitation_gate import check_elicitation

    result = check_elicitation(
        server_name="cloudflare-api",
        request_type="input",
        parameters={"field": "api_key"},
        block_patterns=[],
    )
    assert result["blocked"] is False


def test_block_pattern_matches():
    from elicitation_gate import check_elicitation

    result = check_elicitation(
        server_name="cloudflare-api",
        request_type="input",
        parameters={"field": "delete_zone"},
        block_patterns=["delete_.*"],
    )
    assert result["blocked"] is True


def test_block_pattern_no_match():
    from elicitation_gate import check_elicitation

    result = check_elicitation(
        server_name="cloudflare-api",
        request_type="input",
        parameters={"field": "list_zones"},
        block_patterns=["delete_.*"],
    )
    assert result["blocked"] is False


def test_audit_entry_written(tmp_path: Path):
    from elicitation_gate import write_elicitation_audit

    write_elicitation_audit(
        audit_dir=tmp_path,
        event_type="request",
        server_name="ccsm",
        details={"type": "input"},
    )

    audit_file = tmp_path / "elicitation-events.jsonl"
    assert audit_file.is_file()
    entry = json.loads(audit_file.read_text().strip())
    assert entry["server_name"] == "ccsm"
    assert entry["event_type"] == "request"
```

- [ ] **Step 2: Implement and run tests**

```python
# scripts/elicitation-gate.py
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Elicitation + ElicitationResult hook: audit logging and MCP gating.

Logs MCP elicitation events. Optionally blocks requests matching patterns
using hookSpecificOutput with action: "decline".

Usage:
    Hook:  uv run elicitation-gate.py request  (reads JSON from stdin)
    Hook:  uv run elicitation-gate.py result   (reads JSON from stdin)
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import typer
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed

app = typer.Typer(help="MCP elicitation gate.", no_args_is_help=True)


class McpConfig(BaseModel):
    audit_elicitations: bool = True
    block_patterns: list[str] = Field(default_factory=list)


class ElicitationPayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    server_name: str = ""
    request_type: str = ""
    parameters: dict = Field(default_factory=dict)


class ElicitationResultPayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    server_name: str = ""
    result: dict = Field(default_factory=dict)


def check_elicitation(
    *,
    server_name: str,
    request_type: str,
    parameters: dict,
    block_patterns: list[str],
) -> dict:
    """Check if an elicitation request should be blocked.

    Returns dict with "blocked" bool and "matched_pattern" str.
    """
    # Serialize the request for pattern matching
    searchable = json.dumps({"server": server_name, "type": request_type, **parameters})

    for pattern in block_patterns:
        try:
            if re.search(pattern, searchable):
                return {"blocked": True, "matched_pattern": pattern}
        except re.error:
            continue

    return {"blocked": False, "matched_pattern": ""}


def write_elicitation_audit(
    *,
    audit_dir: Path,
    event_type: str,
    server_name: str,
    details: dict,
) -> None:
    """Write elicitation event to audit trail."""
    audit_dir.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "server_name": server_name,
        **details,
    }
    with (audit_dir / "elicitation-events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def _get_audit_dir(cwd: str) -> Path:
    slug = cwd.replace("/", "-") if cwd else "-unknown"
    return Path.home() / ".claude" / "projects" / slug / "memory" / "audit"


@app.command("request")
def handle_request() -> None:
    """Elicitation hook entry point."""
    payload = ElicitationPayload.model_validate_json(sys.stdin.read())
    config = resolve_typed(McpConfig, "mcp")

    # Audit
    if config.audit_elicitations:
        write_elicitation_audit(
            audit_dir=_get_audit_dir(payload.cwd),
            event_type="request",
            server_name=payload.server_name,
            details={"type": payload.request_type, "parameters": payload.parameters},
        )

    # Check block patterns
    result = check_elicitation(
        server_name=payload.server_name,
        request_type=payload.request_type,
        parameters=payload.parameters,
        block_patterns=config.block_patterns,
    )

    if result["blocked"]:
        # Use hookSpecificOutput to decline (NOT exit 2)
        output = {
            "hookSpecificOutput": {
                "hookEventName": "Elicitation",
                "action": "decline",
            }
        }
        print(json.dumps(output))

    raise typer.Exit(0)


@app.command("result")
def handle_result() -> None:
    """ElicitationResult hook entry point."""
    payload = ElicitationResultPayload.model_validate_json(sys.stdin.read())
    config = resolve_typed(McpConfig, "mcp")

    if config.audit_elicitations:
        write_elicitation_audit(
            audit_dir=_get_audit_dir(payload.cwd),
            event_type="result",
            server_name=payload.server_name,
            details={"result": payload.result},
        )

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
```

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/test_elicitation_gate.py -v`
Expected: 4 PASS

- [ ] **Step 3: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add scripts/elicitation-gate.py tests/test_elicitation_gate.py
git commit -m "feat: add elicitation-gate for Elicitation/ElicitationResult hooks"
```

---

### Task 10: Update `hooks.json` and finalize

**Files:**
- Modify: `hooks/hooks.json`
- Modify: `CHANGELOG.md`
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Replace `hooks/hooks.json` with the full 13-event configuration**

Use the exact JSON from the design spec section 4. The complete file is defined in `docs/plans/2026-03-18-hook-enforcement-architecture-design.md` lines 300-465.

- [ ] **Step 2: Verify JSON is valid**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run python -c "import json; json.load(open('hooks/hooks.json'))"`
Expected: No error

- [ ] **Step 3: Bump version in `.claude-plugin/plugin.json` to 1.3.0**

Read the current plugin.json, update the `"version"` field from `"1.2.0"` to `"1.3.0"`.

- [ ] **Step 4: Update CHANGELOG.md**

Add a new entry at the top under `## [1.3.0]` documenting:
- Shared frontmatter config library (idea 73)
- accessibility-config.py refactored to use shared library
- 7 new hook scripts covering 10 new hook events
- hooks.json expanded from 3 to 13 event types
- New frontmatter config namespaces: enforcement, compaction, worktree, audit, mcp

- [ ] **Step 5: Run full test suite**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run pytest tests/ -v`
Expected: All tests pass (existing + new)

- [ ] **Step 6: Commit**

```bash
cd /home/deathnerd/projects/infinite-room-labs/agent-ops
git add hooks/hooks.json .claude-plugin/plugin.json CHANGELOG.md
git commit -m "feat: expand hook registry to 13 events, bump to 1.3.0"
```
