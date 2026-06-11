"""Tests for _shared.paths module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from _shared.paths import cwd_slug, get_audit_dir, project_dir


def test_cwd_slug_converts_path() -> None:
    """Slashes are replaced with dashes."""
    assert cwd_slug("/home/user/project") == "-home-user-project"


def test_cwd_slug_no_lstrip() -> None:
    """Leading dash from the root slash is preserved."""
    result = cwd_slug("/home/user/project")
    assert result.startswith("-")


def test_cwd_slug_replaces_dots_and_underscores() -> None:
    """Every non-alphanumeric char becomes a dash (Claude Code's actual rule).

    Verified against a live slug: /tmp/slug.test_x -> -tmp-slug-test-x.
    """
    assert cwd_slug("/tmp/slug.test_x") == "-tmp-slug-test-x"


def test_cwd_slug_dotted_dir_double_dash() -> None:
    """A dot-directory yields a double dash, matching live ~/.claude/projects."""
    assert cwd_slug("/home/user/.config/fish") == "-home-user--config-fish"


def test_cwd_slug_preserves_case() -> None:
    """Case is preserved (live evidence: -home-deathnerd-Downloads)."""
    assert cwd_slug("/home/user/Downloads") == "-home-user-Downloads"


def test_cwd_slug_defaults_to_project_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    """None input keys off project_dir (CLAUDE_PROJECT_DIR, then cwd)."""
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    with patch.object(Path, "cwd", return_value=Path("/fake/cwd")):
        result = cwd_slug(None)
    assert result == "-fake-cwd"


def test_project_dir_prefers_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """CLAUDE_PROJECT_DIR wins over both the fallback and the process cwd,
    so hooks running from subdirs/worktrees resolve one consistent slug."""
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", "/project/root")
    assert project_dir("/somewhere/else") == Path("/project/root")


def test_project_dir_fallback_then_cwd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    assert project_dir("/explicit") == Path("/explicit")
    with patch.object(Path, "cwd", return_value=Path("/fake/cwd")):
        assert project_dir(None) == Path("/fake/cwd")


def test_get_audit_dir_creates_directory(tmp_path: Path) -> None:
    """get_audit_dir creates the full directory tree."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    with patch.object(Path, "home", return_value=fake_home):
        audit_dir = get_audit_dir("/some/project")
    assert audit_dir.exists()
    assert audit_dir.is_dir()
    assert str(audit_dir).endswith("memory/audit")
