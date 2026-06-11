"""Tests for worktree-lifecycle.py -- WorktreeCreate / WorktreeRemove hooks."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Generator

import pytest


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

    def test_copy_hooks_skips_non_executable(self, git_repo: Path) -> None:
        """Non-executable files in hooks/ should not be copied."""
        from worktree_lifecycle import copy_git_hooks

        # Add a non-executable file to hooks dir (e.g. a .sample file)
        sample = git_repo / ".git" / "hooks" / "pre-commit.sample"
        sample.write_text("#!/bin/sh\n# sample\n")
        # Ensure it is NOT executable
        sample.chmod(stat.S_IRUSR | stat.S_IWUSR)

        wt_path = git_repo / "worktrees" / "test-wt2"
        subprocess.run(
            ["git", "worktree", "add", str(wt_path), "-b", "test-branch2"],
            check=True,
            capture_output=True,
            cwd=str(git_repo),
        )

        copied = copy_git_hooks(main_repo=git_repo, worktree=wt_path)

        # pre-commit should be copied, pre-commit.sample should not
        assert "pre-commit" in copied
        assert "pre-commit.sample" not in copied


class TestCheckEnvFiles:
    """Tests for check_env_files()."""

    def test_check_env_files_finds_env(self, tmp_path: Path) -> None:
        """Create .env file, verify 1 warning."""
        from worktree_lifecycle import check_env_files

        (tmp_path / ".env").write_text("SECRET=hunter2\n")
        warnings = check_env_files(tmp_path)
        assert len(warnings) == 1
        assert ".env" in warnings[0]

    def test_check_env_files_clean(self, tmp_path: Path) -> None:
        """No .env files, 0 warnings."""
        from worktree_lifecycle import check_env_files

        warnings = check_env_files(tmp_path)
        assert len(warnings) == 0

    def test_check_env_files_skips_example_and_envrc(self, tmp_path: Path) -> None:
        """Should skip .env.example and .envrc."""
        from worktree_lifecycle import check_env_files

        (tmp_path / ".env.example").write_text("SECRET=placeholder\n")
        (tmp_path / ".envrc").write_text("use flake\n")
        warnings = check_env_files(tmp_path)
        assert len(warnings) == 0

    def test_check_env_files_finds_dotenv_variants(self, tmp_path: Path) -> None:
        """Should detect .env.local, .env.production, etc."""
        from worktree_lifecycle import check_env_files

        (tmp_path / ".env.local").write_text("SECRET=local\n")
        (tmp_path / ".env.production").write_text("SECRET=prod\n")
        warnings = check_env_files(tmp_path)
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
            input=json.dumps({"worktree_name": "feat-wt", "branch": "feat-x"}),
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
            input=json.dumps({"worktree_name": "branchless-wt"}),
        )
        assert result.exit_code == 0, result.output
        assert (git_repo / ".worktrees" / "branchless-wt").is_dir()
