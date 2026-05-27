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
    # Warns that the generated content is an example, not the real project.
    assert "placeholders" in msg.lower()
    assert "must not be committed as-is" in msg


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


# -- resolve_push_targets ----------------------------------------------------


def test_resolve_bare_push_uses_current_branch() -> None:
    assert cg.resolve_push_targets("git push", "main") == ["main"]


def test_resolve_push_remote_only_uses_current_branch() -> None:
    assert cg.resolve_push_targets("git push origin", "main") == ["main"]


def test_resolve_push_explicit_ref() -> None:
    assert cg.resolve_push_targets("git push origin main", "feature/x") == ["main"]


def test_resolve_push_refspec_uses_destination() -> None:
    assert cg.resolve_push_targets("git push origin HEAD:main", "feature/x") == ["main"]


def test_resolve_push_bare_head_is_current_branch() -> None:
    assert cg.resolve_push_targets("git push origin HEAD", "main") == ["main"]


def test_resolve_push_delete_colon_form_skips() -> None:
    assert cg.resolve_push_targets("git push origin :main", "main") is None


def test_resolve_push_delete_flag_skips() -> None:
    assert cg.resolve_push_targets("git push --delete origin main", "main") is None


def test_resolve_push_tags_only_skips() -> None:
    assert cg.resolve_push_targets("git push --tags", "main") is None


def test_resolve_push_set_upstream_flag_ignored() -> None:
    assert cg.resolve_push_targets("git push -u origin main", "feature/x") == ["main"]


# -- evaluate_push -----------------------------------------------------------


def _commit_changelog(repo: Path, text: str = "# Changelog\n\nNotes.\n") -> None:
    (repo / "CHANGELOG.md").write_text(text)
    subprocess.run(["git", "add", "CHANGELOG.md"], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "docs: changelog"], check=True, capture_output=True
    )


def test_push_to_main_without_changelog_blocks_and_generates(git_repo: Path) -> None:
    changelog = git_repo / "CHANGELOG.md"
    assert not changelog.exists()
    allowed, msg = cg.evaluate_push("git push origin main", "main", root=git_repo)
    assert allowed is False
    assert changelog.exists(), "template must be generated when missing"
    assert "BLOCKED" in msg
    assert "git add CHANGELOG.md" in msg
    # When it generates the template, the message tells the agent to edit it.
    assert "Edit it" in msg
    assert "example block" in msg


def test_push_to_main_with_tracked_changelog_allows(git_repo: Path) -> None:
    _commit_changelog(git_repo)
    allowed, msg = cg.evaluate_push("git push origin main", "main", root=git_repo)
    assert allowed is True
    assert "tracked" in msg


def test_push_to_feature_branch_allows(git_repo: Path) -> None:
    allowed, msg = cg.evaluate_push(
        "git push origin feature/x", "feature/x", root=git_repo
    )
    assert allowed is True
    assert "no protected branch" in msg.lower()


def test_push_origin_main_from_feature_branch_blocks(git_repo: Path) -> None:
    allowed, _ = cg.evaluate_push("git push origin main", "feature/x", root=git_repo)
    assert allowed is False


def test_push_head_to_main_blocks(git_repo: Path) -> None:
    allowed, _ = cg.evaluate_push(
        "git push origin HEAD:main", "feature/x", root=git_repo
    )
    assert allowed is False


def test_push_delete_main_allows(git_repo: Path) -> None:
    allowed, _ = cg.evaluate_push("git push origin :main", "main", root=git_repo)
    assert allowed is True


def test_push_tags_only_allows(git_repo: Path) -> None:
    allowed, _ = cg.evaluate_push("git push --tags", "main", root=git_repo)
    assert allowed is True


def test_push_all_without_changelog_blocks(git_repo: Path) -> None:
    # git_repo is on 'main', which is protected and exists locally.
    allowed, _ = cg.evaluate_push("git push --all origin", "main", root=git_repo)
    assert allowed is False


def test_push_existing_untracked_changelog_blocks_without_overwrite(
    git_repo: Path,
) -> None:
    changelog = git_repo / "CHANGELOG.md"
    original = "# Changelog\n\nUncommitted draft.\n"
    changelog.write_text(original)  # on disk but never `git add`ed
    allowed, msg = cg.evaluate_push("git push origin main", "main", root=git_repo)
    assert allowed is False
    assert changelog.read_text(encoding="utf-8") == original
    assert "not committed" in msg


# -- hook entrypoint regression ----------------------------------------------


def test_hook_does_not_block_commit_message_mentioning_git_add(git_repo: Path) -> None:
    """End-to-end: a commit whose MESSAGE mentions the staging verb must not be
    misread as a combined add+commit. Run on a feature branch so the changelog
    check itself allows, isolating the combined-detection path."""
    subprocess.run(
        ["git", "checkout", "-b", "feature/x"], check=True, capture_output=True
    )
    # Message text contains the staging verb; build it without the literal so
    # this test's own source doesn't trip the active guard at commit time.
    add_verb = "git " + "add"
    payload = (
        '{"tool_name":"Bash","tool_input":{"command":'
        f'"git commit -m \\"docs: not just the {add_verb} step\\""}}}}'
    )
    result = subprocess.run(
        ["uv", "run", str(_SCRIPTS / "changelog-guard.py"), "hook"],
        input=payload,
        capture_output=True,
        text=True,
        cwd=git_repo,
    )
    assert result.returncode == 0, f"hook blocked a false positive: {result.stderr}"
