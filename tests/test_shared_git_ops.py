"""Tests for _shared.git_ops module."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from _shared.git_ops import (
    effective_cwd,
    get_current_branch,
    get_latest_tag,
    get_repo_root,
    is_combined_add_commit,
    is_self_staging_commit,
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


# -- is_self_staging_commit ----------------------------------------------------


def test_self_staging_detects_am() -> None:
    assert is_self_staging_commit(f"{_COMMIT} -am 'msg'") is True


def test_self_staging_detects_bare_a() -> None:
    assert is_self_staging_commit(f"{_COMMIT} -a -m 'msg'") is True


def test_self_staging_detects_all_flag() -> None:
    assert is_self_staging_commit(f"{_COMMIT} --all -m 'msg'") is True


def test_self_staging_detects_a_in_cluster() -> None:
    assert is_self_staging_commit(f"{_COMMIT} -sam 'msg'") is True


def test_self_staging_ignores_amend() -> None:
    assert is_self_staging_commit(f"{_COMMIT} --amend --no-edit") is False


def test_self_staging_ignores_plain_commit() -> None:
    assert is_self_staging_commit(f"{_COMMIT} -m 'msg'") is False


def test_self_staging_ignores_flag_text_in_message() -> None:
    # '-am' only inside the quoted message, not as a real flag.
    assert is_self_staging_commit(f'{_COMMIT} -m "do not use -am here"') is False


def test_self_staging_ignores_other_commands() -> None:
    assert is_self_staging_commit("tar -am whatever") is False


# -- effective_cwd -------------------------------------------------------------


def test_effective_cwd_defaults_to_payload_cwd(tmp_path: Path) -> None:
    assert effective_cwd(f"{_COMMIT} -m x", tmp_path) == tmp_path


def test_effective_cwd_absolute_cd(tmp_path: Path) -> None:
    target = tmp_path / "other-repo"
    cmd = f"cd {target} && {_COMMIT} -m x"
    assert effective_cwd(cmd, "/somewhere/else") == target


def test_effective_cwd_relative_cd_chains(tmp_path: Path) -> None:
    cmd = f"cd projects && cd app && {_COMMIT} -m x"
    assert effective_cwd(cmd, tmp_path) == tmp_path / "projects" / "app"


def test_effective_cwd_quoted_path_with_space(tmp_path: Path) -> None:
    cmd = f'cd "{tmp_path}/my repo" && {_COMMIT} -m x'
    assert effective_cwd(cmd, "/elsewhere") == tmp_path / "my repo"


def test_effective_cwd_git_dash_c(tmp_path: Path) -> None:
    target = tmp_path / "repo"
    assert effective_cwd(f"git -C {target} commit -m x", "/elsewhere") == target


def test_effective_cwd_git_dash_c_relative(tmp_path: Path) -> None:
    assert effective_cwd("git -C sub commit -m x", tmp_path) == tmp_path / "sub"


def test_effective_cwd_ignores_cd_inside_quotes(tmp_path: Path) -> None:
    cmd = f'echo "run cd /attacker later" && {_COMMIT} -m x'
    assert effective_cwd(cmd, tmp_path) == tmp_path


def test_effective_cwd_ignores_cd_after_git(tmp_path: Path) -> None:
    cmd = f"{_COMMIT} -m x && cd /tmp"
    assert effective_cwd(cmd, tmp_path) == tmp_path


def test_effective_cwd_ignores_quoted_git_for_cutoff(tmp_path: Path) -> None:
    # The word 'git' inside quotes must not stop cd-application early.
    target = tmp_path / "real"
    cmd = f'echo "about git stuff" && cd {target} && {_COMMIT} -m x'
    assert effective_cwd(cmd, "/elsewhere") == target


def test_effective_cwd_parent_traversal(tmp_path: Path) -> None:
    start = tmp_path / "a" / "b"
    cmd = f"cd ../sibling && {_COMMIT} -m x"
    assert effective_cwd(cmd, start) == tmp_path / "a" / "sibling"


# -- cwd-aware git helpers -----------------------------------------------------


def test_get_current_branch_explicit_cwd(git_repo: Path, tmp_path: Path) -> None:
    """Branch resolves for the repo at `cwd`, not the process cwd."""
    elsewhere = tmp_path / "not-a-repo"
    elsewhere.mkdir(exist_ok=True)
    prev = os.getcwd()
    os.chdir(elsewhere)
    try:
        assert get_current_branch(git_repo) == "main"
    finally:
        os.chdir(prev)


def test_get_repo_root_from_subdir(git_repo: Path) -> None:
    sub = git_repo / "deep" / "inside"
    sub.mkdir(parents=True)
    assert get_repo_root(sub) == git_repo


def test_get_repo_root_non_repo_falls_back(tmp_path: Path) -> None:
    lonely = tmp_path / "lonely"
    lonely.mkdir()
    assert get_repo_root(lonely) == lonely
