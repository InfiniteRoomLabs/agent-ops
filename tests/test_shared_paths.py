"""Tests for _shared.paths module."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from _shared.paths import cwd_slug, get_audit_dir


def test_cwd_slug_converts_path() -> None:
    """Slashes are replaced with dashes."""
    assert cwd_slug("/home/user/project") == "-home-user-project"


def test_cwd_slug_no_lstrip() -> None:
    """Leading dash from the root slash is preserved."""
    result = cwd_slug("/home/user/project")
    assert result.startswith("-")


def test_cwd_slug_defaults_to_cwd() -> None:
    """None input uses Path.cwd()."""
    with patch.object(Path, "cwd", return_value=Path("/fake/cwd")):
        result = cwd_slug(None)
    assert result == "-fake-cwd"


def test_get_audit_dir_creates_directory(tmp_path: Path) -> None:
    """get_audit_dir creates the full directory tree."""
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    with patch.object(Path, "home", return_value=fake_home):
        audit_dir = get_audit_dir("/some/project")
    assert audit_dir.exists()
    assert audit_dir.is_dir()
    assert str(audit_dir).endswith("memory/audit")
