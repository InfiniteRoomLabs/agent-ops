"""Tests for teammate-gate.py."""

from __future__ import annotations

import importlib
import json
import subprocess
from pathlib import Path

import pytest
from typer.testing import CliRunner

# teammate-gate.py uses a hyphen, so we use importlib to load it.
_mod = importlib.import_module("teammate-gate")
check_encoding = _mod.check_encoding
check_env_files = _mod.check_env_files
check_agent_dirs = _mod.check_agent_dirs
classify_violations = _mod.classify_violations
EnforcementConfig = _mod.EnforcementConfig

runner = CliRunner()


def _init_repo(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-b", "main"], check=True, capture_output=True, cwd=path)
    subprocess.run(
        ["git", "config", "user.email", "t@t.co"], check=True, capture_output=True, cwd=path
    )
    subprocess.run(
        ["git", "config", "user.name", "T"], check=True, capture_output=True, cwd=path
    )


def test_encoding_check_finds_smart_quotes(tmp_path: Path) -> None:
    """Markdown file containing U+201C left double quotation mark triggers a violation."""
    md = tmp_path / "doc.md"
    md.write_text("Hello \u201cworld\u201d\n", encoding="utf-8")
    violations = check_encoding([md])
    assert len(violations) == 1
    assert violations[0]["type"] == "encoding"
    assert violations[0]["severity"] == "fixable"


def test_encoding_check_clean_file(tmp_path: Path) -> None:
    """A markdown file with only ASCII content produces no violations."""
    md = tmp_path / "clean.md"
    md.write_text("# Title\n\nJust plain ASCII text.\n", encoding="utf-8")
    violations = check_encoding([md])
    assert len(violations) == 0


def test_env_file_check_finds_env(tmp_path: Path) -> None:
    """A .env file path triggers a security violation."""
    env = tmp_path / ".env"
    violations = check_env_files([env])
    assert len(violations) == 1
    assert violations[0]["type"] == "env_files"
    assert violations[0]["severity"] == "security"


def test_agent_dir_check_finds_claude_dir(tmp_path: Path) -> None:
    """A file inside .claude/ triggers a security violation."""
    agent_file = tmp_path / ".claude" / "settings.json"
    violations = check_agent_dirs([agent_file])
    assert len(violations) == 1
    assert violations[0]["type"] == "agent_dirs"
    assert violations[0]["severity"] == "security"


def test_classify_violations() -> None:
    """Mixed violations split correctly into fixable and security buckets."""
    violations = [
        {"type": "encoding", "file": "a.md", "message": "smart quotes", "severity": "fixable"},
        {"type": "env_files", "file": ".env", "message": "env file", "severity": "security"},
        {"type": "agent_dirs", "file": ".claude/x", "message": "agent dir", "severity": "security"},
        {"type": "encoding", "file": "b.md", "message": "em dash", "severity": "fixable"},
    ]
    fixable, security = classify_violations(violations)
    assert len(fixable) == 2
    assert len(security) == 2
    assert all(v["severity"] == "fixable" for v in fixable)
    assert all(v["severity"] == "security" for v in security)


# ---------------------------------------------------------------------------
# Changed-file discovery (cwd-aware, -z, untracked dirs)
# ---------------------------------------------------------------------------


def test_get_changed_files_sees_inside_untracked_directory(tmp_path: Path) -> None:
    """Files INSIDE a new untracked directory must be listed individually
    (plain porcelain reports just `newdir/` and hides the contents)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "newdir").mkdir()
    (repo / "newdir" / "doc.md").write_text("hello\n", encoding="utf-8")

    files = _mod._get_changed_files(repo)
    assert Path("newdir/doc.md") in files


def test_get_changed_files_preserves_spaced_paths(tmp_path: Path) -> None:
    """-z output is unquoted: paths with spaces must come back unmangled."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "my notes.md").write_text("hello\n", encoding="utf-8")

    files = _mod._get_changed_files(repo)
    assert Path("my notes.md") in files


def test_get_changed_files_rename_uses_new_path(tmp_path: Path) -> None:
    """For a staged rename, the NEW path is reported and the original-path
    field is skipped (not misread as a separate changed file)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "old.md").write_text("content\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], check=True, capture_output=True, cwd=repo)
    subprocess.run(
        ["git", "commit", "-m", "init"], check=True, capture_output=True, cwd=repo
    )
    subprocess.run(
        ["git", "mv", "old.md", "new.md"], check=True, capture_output=True, cwd=repo
    )

    files = _mod._get_changed_files(repo)
    assert Path("new.md") in files
    assert Path("old.md") not in files


# ---------------------------------------------------------------------------
# Hook entrypoints: payload cwd (worktree) handling
# ---------------------------------------------------------------------------


def _patch_config(monkeypatch: pytest.MonkeyPatch, seen: list) -> None:
    """Replace frontmatter config resolution with defaults, recording cwd."""

    def fake_resolve_typed(model, namespace, cwd=None, home_override=None):
        seen.append(cwd)
        return EnforcementConfig()

    monkeypatch.setattr(_mod, "resolve_typed", fake_resolve_typed)


def test_idle_validates_payload_cwd_not_process_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A teammate in a worktree elsewhere must be validated against THAT tree.

    The repo at payload cwd has an encoding violation inside an untracked
    directory; the process cwd is a clean, unrelated directory. The old code
    ran git in the process cwd and silently passed (check bypassed)."""
    repo = tmp_path / "worktree"
    _init_repo(repo)
    (repo / "newdir").mkdir()
    (repo / "newdir" / "bad.md").write_text("\u201csmart\u201d\n", encoding="utf-8")

    elsewhere = tmp_path / "elsewhere"
    _init_repo(elsewhere)  # clean repo: process-cwd validation finds nothing
    monkeypatch.chdir(elsewhere)

    seen: list = []
    _patch_config(monkeypatch, seen)

    result = runner.invoke(
        _mod.app, ["idle"], input=json.dumps({"cwd": str(repo)})
    )
    assert result.exit_code == 2
    assert "bad.md" in result.output
    assert seen == [repo]  # config resolved against the payload cwd


def test_completed_security_violation_in_payload_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """.env created in the teammate's worktree -> hard stop JSON on stdout."""
    repo = tmp_path / "worktree"
    _init_repo(repo)
    (repo / ".env").write_text("SECRET=hunter2\n", encoding="utf-8")

    elsewhere = tmp_path / "elsewhere"
    _init_repo(elsewhere)
    monkeypatch.chdir(elsewhere)

    _patch_config(monkeypatch, [])

    result = runner.invoke(
        _mod.app, ["completed"], input=json.dumps({"cwd": str(repo)})
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["continue"] is False
    assert ".env" in data["stopReason"]


def test_idle_malformed_payload_falls_back_to_process_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Malformed stdin -> fall back to process cwd (clean repo -> exit 0)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    monkeypatch.chdir(repo)

    _patch_config(monkeypatch, [])

    result = runner.invoke(_mod.app, ["idle"], input="this is not json")
    assert result.exit_code == 0
