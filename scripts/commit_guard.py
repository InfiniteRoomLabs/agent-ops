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
    # Ruby (must be before PHP 'vendor/' to avoid shadowing)
    IgnoredPattern("vendor/bundle/", "Ruby"),
    # PHP
    IgnoredPattern("vendor/", "PHP"),
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

# ---------------------------------------------------------------------------
# Pydantic models for hook JSON payload
# ---------------------------------------------------------------------------


class ToolInput(BaseModel):
    command: str = ""


class HookPayload(BaseModel):
    tool_name: str = ""
    tool_input: ToolInput = ToolInput()

# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------


def matches(file_path: str, pattern: str) -> bool:
    """Match a pattern against a staged file path.

    If the pattern ends with '/', strip the slash and check if any path
    component (directory segment) matches via fnmatch. This handles both
    plain names ('vendor/') and globs ('*.egg-info/').

    For multi-segment directory patterns ('vendor/bundle/', '.yarn/cache/'),
    check if the pattern appears as a contiguous path prefix or subsequence.

    Otherwise, fnmatch against the basename.
    """
    if pattern.endswith("/"):
        dir_pattern = pattern.rstrip("/")
        if "/" in dir_pattern:
            normalized = Path(file_path).as_posix()
            return (
                fnmatch(normalized, f"{dir_pattern}/*")
                or fnmatch(normalized, f"*/{dir_pattern}/*")
            )
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


if __name__ == "__main__":
    app()
