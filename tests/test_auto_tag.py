"""Tests for auto-tag.py evaluate_auto_tag function."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

# auto-tag.py has a hyphen so we can't import directly -- add scripts to path
# and import from the module after loading it.
import importlib
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
_mod = importlib.import_module("auto-tag")
evaluate_auto_tag = _mod.evaluate_auto_tag
AutoTagResult = _mod.AutoTagResult


def _write_changelog(path: Path, version: str, *, has_content: bool = True) -> None:
    """Write a minimal CHANGELOG.md with one version section."""
    content = f"# Changelog\n\n## [Unreleased]\n\n## [agency-{version}] - 2026-03-18\n\n"
    if has_content:
        content += "### Added\n- Something important\n\n"
    path.write_text(content)


def _write_manifest(project_dir: Path, version: str) -> None:
    """Write a minimal plugin.json manifest."""
    manifest_dir = project_dir / ".claude-plugin"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "plugin.json").write_text(
        json.dumps({"name": "test", "version": version})
    )


def test_should_tag_when_changelog_ahead(git_repo: Path) -> None:
    """CHANGELOG 1.4.0, tag v1.3.0, manifest 1.4.0 -> should_tag=True."""
    # Create tag v1.3.0
    subprocess.run(
        ["git", "tag", "-a", "v1.3.0", "-m", "Release v1.3.0"],
        check=True,
        capture_output=True,
    )

    _write_changelog(git_repo / "CHANGELOG.md", "1.4.0")
    _write_manifest(git_repo, "1.4.0")

    result = evaluate_auto_tag(git_repo)
    assert result.should_tag is True
    assert result.version == "1.4.0"
    assert result.tag_name == "v1.4.0"
    assert result.manifest_mismatch is False


def test_no_tag_when_already_tagged(git_repo: Path) -> None:
    """CHANGELOG 1.3.0, tag v1.3.0 -> should_tag=False."""
    subprocess.run(
        ["git", "tag", "-a", "v1.3.0", "-m", "Release v1.3.0"],
        check=True,
        capture_output=True,
    )

    _write_changelog(git_repo / "CHANGELOG.md", "1.3.0")
    _write_manifest(git_repo, "1.3.0")

    result = evaluate_auto_tag(git_repo)
    assert result.should_tag is False
    assert "already exists" in result.reason


def test_no_tag_on_manifest_mismatch(git_repo: Path) -> None:
    """CHANGELOG 1.4.0, manifest 1.3.0 -> manifest_mismatch=True."""
    subprocess.run(
        ["git", "tag", "-a", "v1.3.0", "-m", "Release v1.3.0"],
        check=True,
        capture_output=True,
    )

    _write_changelog(git_repo / "CHANGELOG.md", "1.4.0")
    _write_manifest(git_repo, "1.3.0")

    result = evaluate_auto_tag(git_repo)
    assert result.should_tag is False
    assert result.manifest_mismatch is True
    assert "does not match" in result.reason


def test_no_tag_on_empty_changelog_section(git_repo: Path) -> None:
    """Header exists but no content -> should_tag=False."""
    subprocess.run(
        ["git", "tag", "-a", "v1.3.0", "-m", "Release v1.3.0"],
        check=True,
        capture_output=True,
    )

    _write_changelog(git_repo / "CHANGELOG.md", "1.4.0", has_content=False)
    _write_manifest(git_repo, "1.4.0")

    result = evaluate_auto_tag(git_repo)
    assert result.should_tag is False
    assert "no content" in result.reason
