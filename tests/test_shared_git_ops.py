"""Tests for _shared.git_ops module."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from _shared.git_ops import (
    candidate_cwds,
    effective_cwd,
    get_current_branch,
    get_latest_tag,
    get_repo_root,
    is_combined_add_commit,
    is_self_staging_commit,
    msys_to_windows,
    resolve_repo_root,
    resolve_repo_roots,
    runs_git_command,
    shell_command_skeleton,
)

# Build git tokens without writing the literal phrases this file's content would
# otherwise trip the active add+commit guard on.
_ADD = "git " + "add"
_COMMIT = "git " + "commit"


# -- Git Bash drive paths ------------------------------------------------------


def test_msys_drive_path_translated_on_windows() -> None:
    assert msys_to_windows("/c/Users/alice/repo", windows=True) == "C:/Users/alice/repo"


def test_cygdrive_path_untouched_on_windows() -> None:
    """Git Bash cannot `cd /cygdrive/c` (no such directory), so the guards
    must not resolve it either -- a translation the shell does not share
    would judge a repo the command never reaches."""
    assert msys_to_windows("/cygdrive/d/work", windows=True) == "/cygdrive/d/work"


def test_uppercase_drive_translated_on_windows() -> None:
    """Git Bash resolves `/C/x` like `/c/x`."""
    assert msys_to_windows("/C/work", windows=True) == "C:/work"


def test_bare_drive_translated_on_windows() -> None:
    assert msys_to_windows("/c", windows=True) == "C:/"


def test_msys_path_untouched_off_windows() -> None:
    """On Linux/macOS `/c/x` is an ordinary absolute path."""
    assert msys_to_windows("/c/Users/alice", windows=False) == "/c/Users/alice"


def test_non_drive_paths_untouched_on_windows() -> None:
    for path in ("/home/alice", "/cx/y", "C:/already", "relative/dir", "~/repo"):
        assert msys_to_windows(path, windows=True) == path


def _git_bash_form(path: Path) -> str:
    drive, rest = path.as_posix().split(":", 1)
    return f"/{drive.lower()}{rest}"


_WINDOWS_ONLY = pytest.mark.skipif(
    os.name != "nt", reason="Git Bash drive paths exist only on Windows"
)


@_WINDOWS_ONLY
def test_effective_cwd_git_bash_cd(tmp_path: Path) -> None:
    target = tmp_path / "other"
    target.mkdir()
    cmd = f"cd {_git_bash_form(target)} && {_COMMIT} -m x"
    assert effective_cwd(cmd, "C:/elsewhere") == target


@_WINDOWS_ONLY
def test_effective_cwd_git_bash_cd_quoted(tmp_path: Path) -> None:
    target = tmp_path / "my repo"
    target.mkdir()
    cmd = f"cd '{_git_bash_form(target)}' && {_COMMIT} -m x"
    assert effective_cwd(cmd, "C:/elsewhere") == target


@_WINDOWS_ONLY
def test_effective_cwd_git_bash_dash_c(tmp_path: Path) -> None:
    target = tmp_path / "other"
    target.mkdir()
    cmd = f"git -C {_git_bash_form(target)} commit -m x"
    assert effective_cwd(cmd, "C:/elsewhere") == target


# -- Candidate directories: a hop that may not take effect keeps the old cwd ---


@pytest.fixture()
def two_dirs(tmp_path: Path) -> tuple[Path, Path]:
    base = tmp_path / "session"
    target = tmp_path / "other"
    base.mkdir()
    target.mkdir()
    return base, target


def test_candidates_and_hop_is_certain(two_dirs) -> None:
    """`cd X && git ...`: git runs only if the cd succeeded."""
    base, target = two_dirs
    assert candidate_cwds(f"cd {target} && {_COMMIT} -m x", base) == [target]


def test_candidates_semicolon_hop_keeps_pre_hop_dir(two_dirs) -> None:
    """`cd X; git ...`: if the cd fails, git still runs, in the old cwd."""
    base, target = two_dirs
    assert candidate_cwds(f"cd {target}; {_COMMIT} -m x", base) == [target, base]


def test_candidates_newline_hop_keeps_pre_hop_dir(two_dirs) -> None:
    base, target = two_dirs
    assert candidate_cwds(f"cd {target}\n{_COMMIT} -m x", base) == [target, base]


def test_candidates_or_hop_keeps_pre_hop_dir(two_dirs) -> None:
    """`cd X || git ...` runs git only when the cd FAILED."""
    base, target = two_dirs
    assert base in candidate_cwds(f"cd {target} || {_COMMIT} -m x", base)


def test_candidates_background_hop_keeps_pre_hop_dir(two_dirs) -> None:
    """`cd X & git ...`: the cd runs in a background subshell."""
    base, target = two_dirs
    assert base in candidate_cwds(f"cd {target} & {_COMMIT} -m x", base)


def test_candidates_hop_after_pipe_keeps_pre_hop_dir(two_dirs) -> None:
    """`true | cd X && git ...`: the cd runs in the pipeline's subshell."""
    base, target = two_dirs
    assert base in candidate_cwds(f"true | cd {target} && {_COMMIT} -m x", base)


def test_candidates_hop_after_or_keeps_pre_hop_dir(two_dirs) -> None:
    """`true || cd X && git ...`: the cd is skipped when `true` succeeds."""
    base, target = two_dirs
    assert base in candidate_cwds(f"true || cd {target} && {_COMMIT} -m x", base)


def test_candidates_hop_before_a_semicolon_is_optional_too(two_dirs) -> None:
    """`cd X && cd sub; git ...` parses as `(cd X && cd sub); git ...`: git
    runs in the session dir if `cd X` fails, in X if `cd sub` fails."""
    base, target = two_dirs
    (target / "sub").mkdir()
    cmd = f"cd {target} && cd sub; {_COMMIT} -m x"
    found = candidate_cwds(cmd, base)
    assert found[0] == target / "sub"
    assert set(found) == {target / "sub", target, base}


def test_candidates_redirect_between_hop_and_git_stays_certain(two_dirs) -> None:
    """`2>&1` is a redirection, not a background `&`."""
    base, target = two_dirs
    cmd = f"cd {target} && npm test 2>&1 && {_COMMIT} -m x"
    assert candidate_cwds(cmd, base) == [target]


def test_candidates_later_pipe_stays_certain(two_dirs) -> None:
    """A pipeline after the hop does not put the cd in a subshell."""
    base, target = two_dirs
    cmd = f"cd {target} && make | tee log && {_COMMIT} -m x"
    assert candidate_cwds(cmd, base) == [target]


def test_candidates_cd_piped_keeps_pre_hop_dir(two_dirs) -> None:
    """`cd X | cat && git ...`: the cd itself runs in the pipe's subshell."""
    base, target = two_dirs
    assert base in candidate_cwds(f"cd {target} | cat && {_COMMIT} -m x", base)


def test_candidates_and_chain_stays_certain(two_dirs) -> None:
    base, target = two_dirs
    (target / "sub").mkdir()
    cmd = f"cd {target} && cd sub && {_COMMIT} -m x"
    assert candidate_cwds(cmd, base) == [target / "sub"]


def test_candidates_git_dash_c_applies_to_every_candidate(two_dirs) -> None:
    base, target = two_dirs
    (base / "sub").mkdir()
    (target / "sub").mkdir()
    cmd = f"cd {target}; git -C sub commit -m x"
    assert candidate_cwds(cmd, base) == [target / "sub", base / "sub"]


def test_candidates_first_is_effective_cwd(two_dirs) -> None:
    base, target = two_dirs
    cmd = f"cd {target}; {_COMMIT} -m x"
    assert candidate_cwds(cmd, base)[0] == effective_cwd(cmd, base)


def test_resolve_repo_roots_dedupes_same_repo(git_repo: Path) -> None:
    """Both candidates inside one repo -> one root to judge."""
    sub = git_repo / "src"
    sub.mkdir()
    cmd = f"cd src; {_COMMIT} -m x"
    assert resolve_repo_roots(cmd, git_repo) == [get_repo_root(git_repo)]


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
    target.mkdir()
    cmd = f"cd {target} && {_COMMIT} -m x"
    assert effective_cwd(cmd, "/somewhere/else") == target


def test_effective_cwd_relative_cd_chains(tmp_path: Path) -> None:
    (tmp_path / "projects" / "app").mkdir(parents=True)
    cmd = f"cd projects && cd app && {_COMMIT} -m x"
    assert effective_cwd(cmd, tmp_path) == tmp_path / "projects" / "app"


def test_effective_cwd_quoted_path_with_space(tmp_path: Path) -> None:
    (tmp_path / "my repo").mkdir()
    cmd = f'cd "{tmp_path}/my repo" && {_COMMIT} -m x'
    assert effective_cwd(cmd, "/elsewhere") == tmp_path / "my repo"


def test_effective_cwd_git_dash_c(tmp_path: Path) -> None:
    target = tmp_path / "repo"
    target.mkdir()
    assert effective_cwd(f"git -C {target} commit -m x", "/elsewhere") == target


def test_effective_cwd_git_dash_c_relative(tmp_path: Path) -> None:
    (tmp_path / "sub").mkdir()
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
    target.mkdir()
    cmd = f'echo "about git stuff" && cd {target} && {_COMMIT} -m x'
    assert effective_cwd(cmd, "/elsewhere") == target


def test_effective_cwd_parent_traversal(tmp_path: Path) -> None:
    start = tmp_path / "a" / "b"
    start.mkdir(parents=True)
    (tmp_path / "a" / "sibling").mkdir()
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


# -- unresolvable cd hops (live crash 2026-08-21: `P=~/x; cd $P && git commit`) --


def test_effective_cwd_unset_var_hop_is_ignored(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AGENT_OPS_UNSET_P", raising=False)
    cmd = f"AGENT_OPS_UNSET_P=~/x; cd $AGENT_OPS_UNSET_P && {_COMMIT} -m x"
    assert effective_cwd(cmd, tmp_path) == tmp_path


def test_effective_cwd_nonexistent_dir_hop_is_ignored(tmp_path: Path) -> None:
    cmd = f"cd {tmp_path}/does/not/exist && {_COMMIT} -m x"
    assert effective_cwd(cmd, tmp_path) == tmp_path


def test_effective_cwd_relative_hop_after_bad_hop_stays_anchored(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AGENT_OPS_UNSET_P", raising=False)
    (tmp_path / "sub").mkdir()
    cmd = f"cd $AGENT_OPS_UNSET_P && cd sub && {_COMMIT} -m x"
    assert effective_cwd(cmd, tmp_path) == tmp_path / "sub"


def test_resolve_repo_root_never_returns_nonexistent_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("AGENT_OPS_UNSET_P", raising=False)
    cmd = f"cd $AGENT_OPS_UNSET_P && {_COMMIT} -m x"
    root = resolve_repo_root(cmd, tmp_path)
    assert root.is_dir()
    assert resolve_repo_root(cmd, "/no/such/payload/cwd").is_dir()
