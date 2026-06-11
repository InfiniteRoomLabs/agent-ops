"""Tests for auto-tag.py evaluate_auto_tag function."""
from __future__ import annotations

import json
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
triggers_auto_tag = _mod.triggers_auto_tag
tool_call_succeeded = _mod.tool_call_succeeded
determine_release_ref = _mod.determine_release_ref


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


def test_evaluate_uses_project_dir_not_process_cwd(
    git_repo: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """evaluate_auto_tag(project_dir) must read git state from project_dir even
    when the process cwd is somewhere else entirely.

    Setup: CHANGELOG 1.3.0 == tag v1.3.0 in the project repo -> correct answer
    is should_tag=False ("already exists"). The old cwd-split-brain bug ran
    `git tag -l` in the PROCESS cwd (no tags there) and wrongly tagged.
    """
    subprocess.run(
        ["git", "tag", "-a", "v1.3.0", "-m", "Release v1.3.0"],
        check=True,
        capture_output=True,
        cwd=git_repo,
    )
    _write_changelog(git_repo / "CHANGELOG.md", "1.3.0")
    _write_manifest(git_repo, "1.3.0")

    elsewhere = tmp_path_factory.mktemp("elsewhere")
    monkeypatch.chdir(elsewhere)

    result = evaluate_auto_tag(git_repo)
    assert result.should_tag is False
    assert "already exists" in result.reason


# -- Trigger detection (skeleton-based) --


def test_trigger_on_real_gh_pr_merge() -> None:
    assert triggers_auto_tag("gh pr merge 42 --squash --delete-branch") is True


def test_no_trigger_on_quoted_mention() -> None:
    """Echoed text mentioning gh pr merge must NOT trigger tag pushes."""
    assert triggers_auto_tag('echo "next step: gh pr merge 42"') is False


def test_no_trigger_on_heredoc_body() -> None:
    cmd = "cat > notes.md <<EOF\nrun gh pr merge 42 tomorrow\nEOF"
    assert triggers_auto_tag(cmd) is False


def test_no_trigger_on_unrelated_command() -> None:
    assert triggers_auto_tag("git push origin main") is False


# -- tool_response success gate --


@pytest.mark.parametrize(
    "response,expected",
    [
        (None, False),  # absent -> failure
        ("oops", False),  # non-dict -> failure
        ({}, False),  # ambiguous -> failure
        ({"success": True}, True),
        ({"success": False}, False),
        ({"exit_code": 0}, True),
        ({"exit_code": 1}, False),
        ({"returncode": 0}, True),
        ({"is_error": False}, True),
        ({"is_error": True}, False),
        ({"stdout": "merged", "stderr": "", "interrupted": False}, True),
        ({"stdout": "", "stderr": "boom", "interrupted": True}, False),
    ],
)
def test_tool_call_succeeded(response: object, expected: bool) -> None:
    assert tool_call_succeeded(response) is expected


# -- Release ref resolution (local-filesystem remote; no network) --


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, cwd=cwd
    )
    return result.stdout.strip()


def test_determine_release_ref_points_at_remote_default_head(tmp_path: Path) -> None:
    """After a PR merge the local checkout is the stale feature branch; the
    release ref must resolve to the REMOTE default branch head, not local HEAD."""
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "main", str(remote)],
        check=True,
        capture_output=True,
    )

    # Seed the remote's main with commit A
    seed = tmp_path / "seed"
    seed.mkdir()
    _git(["init", "-b", "main"], seed)
    _git(["config", "user.email", "t@t.co"], seed)
    _git(["config", "user.name", "T"], seed)
    (seed / "a.txt").write_text("A\n")
    _git(["add", "."], seed)
    _git(["commit", "-m", "A"], seed)
    _git(["remote", "add", "origin", str(remote)], seed)
    _git(["push", "origin", "main"], seed)

    # Clone (sets origin/HEAD -> main), then sit on a feature branch at A
    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", str(remote), str(clone)],
        check=True,
        capture_output=True,
    )
    _git(["config", "user.email", "t@t.co"], clone)
    _git(["config", "user.name", "T"], clone)
    _git(["checkout", "-b", "feat"], clone)

    # Remote main advances to commit B (the "merged PR") -- clone is stale
    (seed / "b.txt").write_text("B\n")
    _git(["add", "."], seed)
    _git(["commit", "-m", "B"], seed)
    _git(["push", "origin", "main"], seed)
    sha_b = _git(["rev-parse", "main"], seed)

    ref = determine_release_ref(clone)
    assert ref is not None
    assert _git(["rev-parse", ref], clone) == sha_b
    assert _git(["rev-parse", "HEAD"], clone) != sha_b


def test_determine_release_ref_none_without_remote(git_repo: Path) -> None:
    """No origin remote -> fetch fails -> None (caller logs and skips)."""
    assert determine_release_ref(git_repo) is None
