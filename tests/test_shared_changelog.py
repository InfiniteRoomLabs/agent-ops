"""Tests for _shared.changelog module."""
from __future__ import annotations

from pathlib import Path

from _shared.changelog import get_latest_changelog_version, has_content_under_header


SAMPLE_CHANGELOG = """\
# Changelog

## [Unreleased]

## [agency-1.3.0] - 2026-03-18

### Added
- Shared frontmatter config library
- Instructions guard

## [agency-1.2.0] - 2026-03-15

### Added
- Version guard hook
"""


def test_get_latest_version_finds_first(tmp_path: Path) -> None:
    """Normal CHANGELOG returns the first versioned entry."""
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(SAMPLE_CHANGELOG)
    assert get_latest_changelog_version(cl) == "1.3.0"


def test_get_latest_version_skips_unreleased(tmp_path: Path) -> None:
    """[Unreleased] is skipped, first real version is returned."""
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text("# Changelog\n\n## [Unreleased]\n\n## [agency-1.3.0] - 2026-03-18\n")
    assert get_latest_changelog_version(cl) == "1.3.0"


def test_get_latest_version_empty_file(tmp_path: Path) -> None:
    """Empty CHANGELOG returns None."""
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text("")
    assert get_latest_changelog_version(cl) is None


def test_has_content_with_bullet_points(tmp_path: Path) -> None:
    """Section with bullet points returns True."""
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(SAMPLE_CHANGELOG)
    assert has_content_under_header(cl, "1.3.0") is True


def test_has_content_empty_section(tmp_path: Path) -> None:
    """Section with no content at all returns False."""
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(
        "# Changelog\n\n## [agency-2.0.0] - 2026-04-01\n\n## [agency-1.3.0] - 2026-03-18\n"
    )
    assert has_content_under_header(cl, "2.0.0") is False


def test_has_content_stub_section(tmp_path: Path) -> None:
    """Section with only ### sub-headers (no bullets) returns False."""
    cl = tmp_path / "CHANGELOG.md"
    cl.write_text(
        "# Changelog\n\n"
        "## [agency-2.0.0] - 2026-04-01\n\n"
        "### Added\n\n"
        "### Changed\n\n"
        "## [agency-1.3.0] - 2026-03-18\n"
    )
    assert has_content_under_header(cl, "2.0.0") is False
