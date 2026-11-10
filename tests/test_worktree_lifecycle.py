"""Tests for worktree-lifecycle.py -- WorktreeCreate / WorktreeRemove hooks."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Generator

import pytest


def claude_code_create_payload(name: str, cwd: Path) -> dict:
    """WorktreeCreate stdin exactly as Claude Code sends it.

    The common hook fields plus ``hook_event_name`` and ``name`` -- there is no
    ``worktree_name`` and no ``branch``. Schema per the Claude Code hooks
    reference and the 2.1.329 input schema; a subagent launch names the
    worktree ``agent-<id>``.
    """
    return {
        "session_id": "00000000-0000-4000-8000-000000000000",
        "transcript_path": str(cwd / "session.jsonl"),
        "cwd": str(cwd),
        "permission_mode": "default",
        "hook_event_name": "WorktreeCreate",
        "name": name,
    }


def claude_code_remove_payload(worktree_path: Path, cwd: Path) -> dict:
    """WorktreeRemove stdin exactly as Claude Code sends it."""
    return {
        "session_id": "00000000-0000-4000-8000-000000000000",
        "transcript_path": str(cwd / "session.jsonl"),
        "cwd": str(cwd),
        "permission_mode": "default",
        "hook_event_name": "WorktreeRemove",
        "worktree_path": str(worktree_path),
    }


@pytest.fixture()
def git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Git repo with an executable pre-commit hook."""
    prev = os.getcwd()
    os.chdir(tmp_path)
    subprocess.run(["git", "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: initial commit"],
        check=True,
        capture_output=True,
    )

    # Create an executable pre-commit hook in the main repo
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_file = hooks_dir / "pre-commit"
    hook_file.write_text("#!/bin/sh\necho 'pre-commit hook'\n")
    hook_file.chmod(hook_file.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    yield tmp_path
    os.chdir(prev)


class TestCopyHooksToWorktree:
    """Tests for copy_git_hooks()."""

    def test_copy_hooks_to_worktree(self, git_repo: Path) -> None:
        """Create worktree via subprocess, then copy_git_hooks, verify hook exists in resolved git dir."""
        from worktree_lifecycle import copy_git_hooks

        wt_path = git_repo / "worktrees" / "test-wt"
        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "-b", "test-branch"],
            check=True,
            capture_output=True,
            cwd=str(git_repo),
        )

        copied = copy_git_hooks(main_repo=git_repo, worktree=wt_path)

        assert "pre-commit" in copied

        # Resolve the worktree's real git dir
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            cwd=str(wt_path),
        )
        wt_git_dir = Path(result.stdout.strip())
        if not wt_git_dir.is_absolute():
            wt_git_dir = (wt_path / wt_git_dir).resolve()

        hook_in_wt = wt_git_dir / "hooks" / "pre-commit"
        assert hook_in_wt.exists(), f"Expected hook at {hook_in_wt}"
        assert os.access(hook_in_wt, os.X_OK), "Hook should be executable"

    @pytest.mark.skipif(
        os.name == "nt", reason="Windows has no exec bit; Git for Windows runs any hook file"
    )
    def test_copy_hooks_skips_non_executable(self, git_repo: Path) -> None:
        """Non-executable files in hooks/ should not be copied."""
        from worktree_lifecycle import copy_git_hooks

        # A real hook name, but NOT executable, so git would not run it
        disabled = git_repo / ".git" / "hooks" / "post-checkout"
        disabled.write_text("#!/bin/sh\n# disabled\n")
        disabled.chmod(stat.S_IRUSR | stat.S_IWUSR)

        wt_path = git_repo / "worktrees" / "test-wt2"
        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "-b", "test-branch2"],
            check=True,
            capture_output=True,
            cwd=str(git_repo),
        )

        copied = copy_git_hooks(main_repo=git_repo, worktree=wt_path)

        assert "pre-commit" in copied
        assert "post-checkout" not in copied

    def test_copy_hooks_skips_sample_hooks(self, git_repo: Path) -> None:
        """Git never runs `*.sample` hooks, so they are not propagated even
        when executable (git's templates ship them 0755 on Linux, and on
        Windows every file passes the exec check)."""
        from worktree_lifecycle import copy_git_hooks

        sample = git_repo / ".git" / "hooks" / "pre-push.sample"
        sample.write_text("#!/bin/sh\n# sample\n")
        sample.chmod(sample.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        wt_path = git_repo / "worktrees" / "test-wt3"
        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "-b", "test-branch3"],
            check=True,
            capture_output=True,
            cwd=str(git_repo),
        )

        copied = copy_git_hooks(main_repo=git_repo, worktree=wt_path)

        assert "pre-commit" in copied
        assert not [name for name in copied if name.endswith(".sample")], copied


class TestCheckEnvFiles:
    """Tests for check_worktree_env_files()."""

    def test_check_worktree_env_files_finds_env(self, tmp_path: Path) -> None:
        """Create .env file, verify 1 warning."""
        from worktree_lifecycle import check_worktree_env_files

        (tmp_path / ".env").write_text("SECRET=hunter2\n")
        warnings = check_worktree_env_files(tmp_path)
        assert len(warnings) == 1
        assert ".env" in warnings[0]

    def test_check_worktree_env_files_clean(self, tmp_path: Path) -> None:
        """No .env files, 0 warnings."""
        from worktree_lifecycle import check_worktree_env_files

        warnings = check_worktree_env_files(tmp_path)
        assert len(warnings) == 0

    def test_check_worktree_env_files_skips_example_and_envrc(self, tmp_path: Path) -> None:
        """Should skip .env.example and .envrc."""
        from worktree_lifecycle import check_worktree_env_files

        (tmp_path / ".env.example").write_text("SECRET=placeholder\n")
        (tmp_path / ".envrc").write_text("use flake\n")
        warnings = check_worktree_env_files(tmp_path)
        assert len(warnings) == 0

    def test_check_worktree_env_files_finds_dotenv_variants(self, tmp_path: Path) -> None:
        """Should detect .env.local, .env.production, etc."""
        from worktree_lifecycle import check_worktree_env_files

        (tmp_path / ".env.local").write_text("SECRET=local\n")
        (tmp_path / ".env.production").write_text("SECRET=prod\n")
        warnings = check_worktree_env_files(tmp_path)
        assert len(warnings) == 2


class TestCreateCommand:
    """Tests for the WorktreeCreate hook entry point."""

    @pytest.fixture(autouse=True)
    def _hermetic(self, monkeypatch: pytest.MonkeyPatch):
        """Keep the hook hermetic: no real-home audit writes, default config."""
        import worktree_lifecycle as wl

        monkeypatch.setattr(wl, "_write_audit", lambda event: None)
        monkeypatch.setattr(
            wl,
            "resolve_typed",
            lambda model, namespace, **kw: wl.WorktreeConfig(),
        )

    def test_create_from_subdirectory_uses_repo_root(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Invoked from a subdir, .worktrees/ must land at the REPO ROOT,
        not nested inside the subdirectory."""
        import json

        from typer.testing import CliRunner

        import worktree_lifecycle as wl

        subdir = git_repo / "src" / "nested"
        subdir.mkdir(parents=True)
        monkeypatch.chdir(subdir)

        result = CliRunner().invoke(
            wl.app,
            ["create"],
            input=json.dumps({"name": "feat-wt", "branch": "feat-x"}),
        )
        assert result.exit_code == 0, result.output

        root_wt = git_repo / ".worktrees" / "feat-wt"
        assert root_wt.is_dir()
        assert not (subdir / ".worktrees").exists()
        # Hook contract: prints the absolute worktree path on stdout
        assert str(root_wt.resolve()) in result.stdout

    def test_create_branchless_payload_does_not_crash(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A payload without `branch` must still create the worktree."""
        import json

        from typer.testing import CliRunner

        import worktree_lifecycle as wl

        monkeypatch.chdir(git_repo)

        result = CliRunner().invoke(
            wl.app,
            ["create"],
            input=json.dumps({"name": "branchless-wt"}),
        )
        assert result.exit_code == 0, result.output
        assert (git_repo / ".worktrees" / "branchless-wt").is_dir()

    def test_create_accepts_claude_code_payload(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The payload Claude Code really sends (`name`, no `worktree_name`)
        creates <repo root>/.worktrees/<name> and prints its absolute path
        as the last stdout line, which is what the harness reads."""
        import json

        from typer.testing import CliRunner

        import worktree_lifecycle as wl

        monkeypatch.chdir(git_repo)
        name = "agent-a8daf1c9a79ee5133"

        result = CliRunner().invoke(
            wl.app,
            ["create"],
            input=json.dumps(claude_code_create_payload(name, git_repo)),
        )
        assert result.exit_code == 0, result.output

        wt = git_repo / ".worktrees" / name
        assert wt.is_dir()
        last_line = result.stdout.strip().splitlines()[-1]
        assert last_line == str(wt.resolve())

    def test_create_without_name_fails_with_clear_message(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A payload with no `name` must exit non-zero with a readable stderr
        message naming the missing field -- not a pydantic traceback."""
        import json

        from typer.testing import CliRunner

        import worktree_lifecycle as wl

        monkeypatch.chdir(git_repo)
        payload = claude_code_create_payload("unused", git_repo)
        del payload["name"]

        result = CliRunner().invoke(wl.app, ["create"], input=json.dumps(payload))

        assert result.exit_code == 1
        # A handled exit, not an escaped ValidationError
        assert isinstance(result.exception, SystemExit), repr(result.exception)
        assert "`name`" in result.stderr
        assert result.stdout.strip() == ""
        assert not (git_repo / ".worktrees").exists()

    def test_create_rejects_malformed_json_cleanly(
        self, git_repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Non-JSON stdin exits 1 with a message, not a traceback."""
        from typer.testing import CliRunner

        import worktree_lifecycle as wl

        monkeypatch.chdir(git_repo)

        result = CliRunner().invoke(wl.app, ["create"], input="not json")

        assert result.exit_code == 1
        assert isinstance(result.exception, SystemExit), repr(result.exception)
        assert "WorktreeCreate" in result.stderr
        assert result.stdout.strip() == ""


class TestRemoveCommand:
    """Tests for the WorktreeRemove hook entry point."""

    @pytest.fixture()
    def audit(self, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
        """Capture audit events instead of writing to the real home dir."""
        import worktree_lifecycle as wl

        events: list[dict] = []
        monkeypatch.setattr(wl, "_write_audit", events.append)
        monkeypatch.setattr(
            wl,
            "resolve_typed",
            lambda model, namespace, **kw: wl.WorktreeConfig(),
        )
        return events

    def test_remove_accepts_claude_code_payload(
        self, git_repo: Path, audit: list[dict]
    ) -> None:
        """The real WorktreeRemove payload is read via `worktree_path` and
        audited; a worktree with uncommitted work is reported and kept."""
        import json

        from typer.testing import CliRunner

        import worktree_lifecycle as wl

        wt = git_repo / ".worktrees" / "agent-a8daf1c9a79ee5133"
        subprocess.run(
            ["git", "worktree", "add", str(wt)],
            check=True,
            capture_output=True,
            cwd=str(git_repo),
        )
        (wt / "scratch.txt").write_text("uncommitted\n")

        result = CliRunner().invoke(
            wl.app,
            ["remove"],
            input=json.dumps(claude_code_remove_payload(wt, git_repo)),
        )

        # Uncommitted work: the worktree is kept (exit 1) and the audit says so.
        assert result.exit_code == 1, result.output
        assert wt.is_dir()
        assert len(audit) == 1
        assert audit[0]["event"] == "worktree_removed"
        assert audit[0]["path"] == str(wt)
        assert audit[0]["had_uncommitted"] is True
        assert audit[0]["removed"] is False

    def test_remove_without_worktree_path_exits_zero_with_warning(
        self, git_repo: Path, audit: list[dict]
    ) -> None:
        """Removal is debug-only visibility: a payload missing `worktree_path`
        warns on stderr and exits 0 instead of raising."""
        import json

        from typer.testing import CliRunner

        import worktree_lifecycle as wl

        payload = claude_code_remove_payload(git_repo, git_repo)
        del payload["worktree_path"]

        result = CliRunner().invoke(wl.app, ["remove"], input=json.dumps(payload))

        assert result.exit_code == 0
        assert result.exception is None, repr(result.exception)
        assert "`worktree_path`" in result.stderr
        assert audit == []


class TestCleanup:
    """WorktreeRemove deletes safe worktrees; SubagentStop cleans its own."""

    @pytest.fixture(autouse=True)
    def _hermetic(self, monkeypatch: pytest.MonkeyPatch, git_repo: Path):
        import worktree_lifecycle as wl

        monkeypatch.setattr(wl, "_write_audit", lambda event: None)
        monkeypatch.setattr(
            wl, "resolve_typed", lambda model, namespace, **kw: wl.WorktreeConfig()
        )
        monkeypatch.chdir(git_repo)

    def _make(self, git_repo: Path, name: str) -> Path:
        wt = git_repo / ".worktrees" / name
        subprocess.run(
            ["git", "worktree", "add", str(wt)],
            check=True, capture_output=True, cwd=git_repo,
        )
        return wt

    def _branches(self, git_repo: Path) -> str:
        return subprocess.run(
            ["git", "branch", "--list"], capture_output=True, text=True, cwd=git_repo
        ).stdout

    def _commit(self, wt: Path) -> None:
        (wt / "new.txt").write_text("x\n")
        subprocess.run(["git", "add", "."], check=True, capture_output=True, cwd=wt)
        subprocess.run(
            ["git", "commit", "-m", "work"], check=True, capture_output=True, cwd=wt
        )

    def _run(self, cmd: str, payload: dict):
        import json

        from typer.testing import CliRunner

        import worktree_lifecycle as wl

        return CliRunner().invoke(wl.app, [cmd], input=json.dumps(payload))

    def test_remove_deletes_clean_worktree_and_branch(self, git_repo: Path) -> None:
        wt = self._make(git_repo, "clean-wt")
        result = self._run("remove", {"worktree_path": str(wt)})
        assert result.exit_code == 0, result.output
        assert not wt.exists()
        assert "clean-wt" not in self._branches(git_repo)

    def test_remove_keeps_worktree_with_untracked_file(self, git_repo: Path) -> None:
        wt = self._make(git_repo, "dirty-wt")
        (wt / "scratch.txt").write_text("wip\n")
        result = self._run("remove", {"worktree_path": str(wt)})
        assert result.exit_code != 0
        assert wt.is_dir()

    def test_remove_keeps_worktree_with_unmerged_commit(self, git_repo: Path) -> None:
        wt = self._make(git_repo, "ahead-wt")
        self._commit(wt)
        result = self._run("remove", {"worktree_path": str(wt)})
        assert result.exit_code != 0
        assert wt.is_dir()
        assert "ahead-wt" in self._branches(git_repo)

    def test_subagent_stop_removes_clean_worktree(self, git_repo: Path) -> None:
        wt = self._make(git_repo, "agent-abc123")
        payload = {
            "hook_event_name": "SubagentStop",
            "agent_id": "abc123",
            "agent_type": "Explore",
            "stop_hook_active": False,
        }
        result = self._run("subagent-stop", payload)
        assert result.exit_code == 0 and result.stdout == ""
        assert not wt.exists()
        assert "agent-abc123" not in self._branches(git_repo)

    def test_subagent_stop_keeps_worktree_with_commit(self, git_repo: Path) -> None:
        wt = self._make(git_repo, "agent-def456")
        self._commit(wt)
        result = self._run("subagent-stop", {"agent_id": "def456"})
        assert result.exit_code == 0 and result.stdout == ""
        assert wt.is_dir()

    def test_subagent_stop_without_worktree_is_silent(self, git_repo: Path) -> None:
        result = self._run("subagent-stop", {"agent_id": "nope"})
        assert result.exit_code == 0 and result.stdout == ""
