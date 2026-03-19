"""Tests for _shared.git_ops module."""
from __future__ import annotations

import subprocess
from pathlib import Path

from _shared.git_ops import get_current_branch, get_latest_tag


def test_get_current_branch(git_repo: Path) -> None:
    """Returns 'main' for a freshly initialized repo."""
    assert get_current_branch() == "main"


def test_get_latest_tag_none(git_repo: Path) -> None:
    """Returns None when no tags exist."""
    assert get_latest_tag() is None


def test_get_latest_tag_returns_latest(git_repo: Path) -> None:
    """Returns the highest version tag when multiple exist."""
    subprocess.run(
        ["git", "tag", "-a", "v1.0.0", "-m", "Release v1.0.0"],
        check=True, capture_output=True,
    )
    # Create a new commit so we can tag it separately
    (git_repo / "file.txt").write_text("content\n")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: add file"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "tag", "-a", "v1.1.0", "-m", "Release v1.1.0"],
        check=True, capture_output=True,
    )
    assert get_latest_tag() == "v1.1.0"
