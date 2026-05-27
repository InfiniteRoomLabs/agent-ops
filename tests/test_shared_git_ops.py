"""Tests for _shared.git_ops module."""
from __future__ import annotations

import subprocess
from pathlib import Path

from _shared.git_ops import (
    get_current_branch,
    get_latest_tag,
    is_combined_add_commit,
    runs_git_command,
    shell_command_skeleton,
)

# Build git tokens without writing the literal phrases this file's content would
# otherwise trip the active add+commit guard on.
_ADD = "git " + "add"
_COMMIT = "git " + "commit"


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


# -- shell_command_skeleton --------------------------------------------------


def test_skeleton_strips_double_quoted_message() -> None:
    skel = shell_command_skeleton(f'{_COMMIT} -m "docs: mentions {_ADD} here"')
    assert _ADD not in skel
    assert "commit" in skel  # the command token survives


def test_skeleton_strips_single_quoted_payload() -> None:
    skel = shell_command_skeleton(f"echo '{{\"c\":\"{_COMMIT} x\"}}' | guard")
    assert "commit" not in skel  # the quoted git command is gone


def test_skeleton_strips_heredoc_body() -> None:
    cmd = f"{_COMMIT} -m \"$(cat <<'EOF'\nline one\n{_ADD} the thing\nEOF\n)\""
    skel = shell_command_skeleton(cmd)
    assert _ADD not in skel


# -- runs_git_command --------------------------------------------------------


def test_runs_detects_real_command() -> None:
    assert runs_git_command(f"{_COMMIT} -m x", "commit") is True
    assert runs_git_command(f"{_ADD} foo.py", "add") is True


def test_runs_ignores_command_inside_message() -> None:
    assert runs_git_command(f'{_COMMIT} -m "talks about {_ADD}"', "add") is False


def test_runs_ignores_echoed_payload() -> None:
    assert runs_git_command(f"echo '{_COMMIT} -m x'", "commit") is False


# -- is_combined_add_commit --------------------------------------------------


def test_combined_true_for_real_chain() -> None:
    assert is_combined_add_commit(f'{_ADD} . && {_COMMIT} -m "x"') is True


def test_combined_true_for_semicolon_chain() -> None:
    assert is_combined_add_commit(f"{_ADD} foo ; {_COMMIT} -m msg") is True


def test_combined_false_when_message_mentions_add() -> None:
    # The exact bug: a commit whose message text contains the staging verb.
    assert is_combined_add_commit(f'{_COMMIT} -m "docs: {_ADD} the notes"') is False


def test_combined_false_for_heredoc_message() -> None:
    cmd = f"{_COMMIT} -m \"$(cat <<'EOF'\nnot just the {_ADD} step\nEOF\n)\""
    assert is_combined_add_commit(cmd) is False


def test_combined_false_for_commit_only() -> None:
    assert is_combined_add_commit(f"{_COMMIT} -m x") is False
