"""Common git operations."""
from __future__ import annotations
import subprocess


def get_current_branch() -> str:
    """Return the current git branch name."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def get_latest_tag(prefix: str = "v") -> str | None:
    """Return the latest tag string matching {prefix}*, or None.

    Sorted by version (git's -v:refname). Returns the full tag string
    including the prefix (e.g., "v1.3.0").
    """
    result = subprocess.run(
        ["git", "tag", "-l", f"{prefix}*", "--sort=-v:refname"],
        capture_output=True, text=True,
    )
    for line in result.stdout.strip().splitlines():
        tag = line.strip()
        if tag:
            return tag
    return None
