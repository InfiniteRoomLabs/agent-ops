"""Shared fixtures for version-guard tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture()
def git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repo with an initial commit on 'main' branch."""
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
    yield tmp_path
    os.chdir(prev)


@pytest.fixture()
def tagged_repo(git_repo: Path) -> Path:
    """Git repo with a v1.0.0 tag on the initial commit."""
    subprocess.run(
        ["git", "tag", "-a", "v1.0.0", "-m", "Release v1.0.0"],
        check=True,
        capture_output=True,
    )
    return git_repo


@pytest.fixture()
def repo_with_manifest(tagged_repo: Path) -> Path:
    """Tagged repo with a package.json at version 1.0.0."""
    (tagged_repo / "package.json").write_text('{\n  "version": "1.0.0"\n}\n')
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: add package.json"],
        check=True,
        capture_output=True,
    )
    return tagged_repo
