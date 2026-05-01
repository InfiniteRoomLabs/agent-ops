"""Tests for scripts/changelog-guard.py."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load_module() -> Any:
    """Hyphenated filename can't be imported normally; load via spec."""
    spec = importlib.util.spec_from_file_location(
        "changelog_guard", _SCRIPTS / "changelog-guard.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cg = _load_module()


# -- render_template ---------------------------------------------------------


def test_render_template_substitutes_date() -> None:
    out = cg.render_template(today="2026-05-01")
    assert "{{DATE}}" not in out
    assert "2026-05-01" in out


def test_render_template_keeps_canonical_header() -> None:
    out = cg.render_template(today="2026-05-01")
    lines = out.splitlines()
    assert lines[0] == "# Changelog"
    assert "All notable changes to this project will be documented" in lines[2]
    assert "Keep a Changelog" in lines[4]
    assert "Semantic Versioning" in lines[5]


def test_render_template_includes_all_kac_sections() -> None:
    out = cg.render_template(today="2026-05-01")
    for section in ("Added", "Changed", "Deprecated", "Removed", "Fixed", "Security"):
        assert f"### {section}" in out, f"missing section: {section}"


def test_render_template_marks_example_block() -> None:
    out = cg.render_template(today="2026-05-01")
    assert "EXAMPLE BLOCK" in out


# -- generate_changelog ------------------------------------------------------


def test_generate_changelog_writes_file(tmp_path: Path) -> None:
    target = tmp_path / "CHANGELOG.md"
    assert not target.exists()
    written = cg.generate_changelog(target, today="2026-05-01")
    assert written == target
    assert target.exists()
    content = target.read_text(encoding="utf-8")
    assert content.startswith("# Changelog\n")
    assert "2026-05-01" in content


# -- evaluate ----------------------------------------------------------------


def test_evaluate_unprotected_branch_allows(git_repo: Path) -> None:
    subprocess.run(
        ["git", "checkout", "-b", "feature/foo"], check=True, capture_output=True
    )
    allowed, msg = cg.evaluate("feature/foo", root=git_repo)
    assert allowed is True
    assert "not protected" in msg


def test_evaluate_protected_with_staged_changelog_allows(git_repo: Path) -> None:
    (git_repo / "CHANGELOG.md").write_text("# Changelog\n")
    subprocess.run(["git", "add", "CHANGELOG.md"], check=True, capture_output=True)
    allowed, msg = cg.evaluate("main", root=git_repo)
    assert allowed is True
    assert "Good to go" in msg


def test_evaluate_protected_missing_changelog_generates_template(
    git_repo: Path,
) -> None:
    changelog = git_repo / "CHANGELOG.md"
    assert not changelog.exists()
    allowed, msg = cg.evaluate("main", root=git_repo)
    assert allowed is False
    assert changelog.exists(), "template must be generated when missing"
    content = changelog.read_text(encoding="utf-8")
    assert content.startswith("# Changelog\n")
    assert "Keep a Changelog" in content
    assert "Semantic Versioning" in content
    # Message guides the agent to the generated file and tells them what to do.
    assert "EXAMPLE" in msg
    assert "CHANGELOG.md" in msg
    assert "first five lines" in msg.lower() or "header" in msg.lower()


def test_evaluate_protected_existing_changelog_unstaged_blocks_without_regen(
    git_repo: Path,
) -> None:
    changelog = git_repo / "CHANGELOG.md"
    original = "# Changelog\n\nMy real notes.\n"
    changelog.write_text(original)
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add changelog"], check=True, capture_output=True
    )
    # Now make some other staged change and verify changelog isn't overwritten.
    (git_repo / "feature.txt").write_text("x")
    subprocess.run(["git", "add", "feature.txt"], check=True, capture_output=True)

    allowed, msg = cg.evaluate("main", root=git_repo)
    assert allowed is False
    assert changelog.read_text(encoding="utf-8") == original
    assert "without updating CHANGELOG.md" in msg


def test_evaluate_release_branch_is_protected(git_repo: Path) -> None:
    subprocess.run(
        ["git", "checkout", "-b", "release/1.2.0"], check=True, capture_output=True
    )
    allowed, _ = cg.evaluate("release/1.2.0", root=git_repo)
    assert allowed is False
