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


# ---------------------------------------------------------------------------
# Encoding check scoped to the files the teammate itself edited
# ---------------------------------------------------------------------------

_SESSION = "00000000-0000-4000-8000-000000000000"
_AGENT = "aworker-0123456789abcdef"


def _tool_use(name: str, **tool_input: str) -> str:
    """One assistant transcript record holding a single tool call, shaped
    like Claude Code's (2.1.329) transcript lines."""
    return json.dumps(
        {
            "type": "assistant",
            "agentId": _AGENT,
            "sessionId": _SESSION,
            "isSidechain": True,
            "message": {
                "role": "assistant",
                "type": "message",
                "content": [
                    {"type": "tool_use", "id": "toolu_1", "name": name, "input": tool_input}
                ],
            },
        }
    )


def _teammate_session(tmp_path: Path, *records: str) -> Path:
    """Session transcript plus the teammate's own transcript where Claude Code
    keeps it: <session transcript minus .jsonl>/subagents/agent-<id>.jsonl.
    Returns the session transcript path (what the payload carries)."""
    project = tmp_path / "projects" / "slug"
    project.mkdir(parents=True)
    session = project / f"{_SESSION}.jsonl"
    session.write_text("", encoding="utf-8")
    sub = project / _SESSION / "subagents"
    sub.mkdir(parents=True)
    (sub / f"agent-{_AGENT}.jsonl").write_text(
        "\n".join(records) + "\n", encoding="utf-8"
    )
    return session


def _teammate_idle(cwd: Path, transcript: Path, agent_id: str = _AGENT) -> str:
    """TeammateIdle stdin as Claude Code sends it: the common fields (with the
    SESSION transcript_path and the teammate's agent_id) plus teammate_name
    and team_name."""
    return json.dumps(
        {
            "session_id": _SESSION,
            "transcript_path": str(transcript),
            "cwd": str(cwd),
            "permission_mode": "auto",
            "agent_id": agent_id,
            "agent_type": "worker",
            "hook_event_name": "TeammateIdle",
            "teammate_name": "worker",
            "team_name": "session-00000000",
        }
    )


def test_files_edited_in_transcript_lists_write_tools_only(tmp_path: Path) -> None:
    transcript = tmp_path / "agent.jsonl"
    transcript.write_text(
        "\n".join(
            [
                _tool_use("Read", file_path="path/to/read.md"),
                _tool_use("Edit", file_path="path/to/a.md", old_string="x", new_string="y"),
                "not json",
                _tool_use("Write", file_path="path/to/b.md", content="z"),
                _tool_use("NotebookEdit", notebook_path="path/to/c.ipynb", new_source="s"),
                _tool_use("Edit", file_path="path/to/a.md", old_string="y", new_string="w"),
            ]
        ),
        encoding="utf-8",
    )
    assert _mod.files_edited_in_transcript(transcript) == [
        Path("path/to/a.md"),
        Path("path/to/b.md"),
        Path("path/to/c.ipynb"),
    ]


def test_idle_ignores_violations_in_files_the_teammate_did_not_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session tree holds someone else's untracked .md with U+2026; the
    teammate edited only a clean file. Blocking it would loop forever, since
    the teammate must not touch that file. Observed live 2026-11-20."""
    tree = tmp_path / "session-repo"
    _init_repo(tree)
    (tree / "docs").mkdir()
    (tree / "docs" / "notes.md").write_text("Later" + chr(0x2026) + "\n", encoding="utf-8")
    mine = tmp_path / "elsewhere" / "README.md"
    mine.parent.mkdir()
    mine.write_text("plain\n", encoding="utf-8")
    transcript = _teammate_session(tmp_path, _tool_use("Write", file_path=str(mine)))
    _patch_config(monkeypatch, [])

    result = runner.invoke(_mod.app, ["idle"], input=_teammate_idle(tree, transcript))

    assert result.exit_code == 0, result.output


def test_idle_flags_violations_in_files_the_teammate_edited_outside_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A teammate working in another repo is judged on what it wrote there."""
    tree = tmp_path / "session-repo"
    _init_repo(tree)
    mine = tmp_path / "other-repo" / "CHANGES.md"
    mine.parent.mkdir()
    mine.write_text(chr(0x201C) + "quoted" + chr(0x201D) + "\n", encoding="utf-8")
    transcript = _teammate_session(tmp_path, _tool_use("Edit", file_path=str(mine)))
    _patch_config(monkeypatch, [])

    result = runner.invoke(_mod.app, ["idle"], input=_teammate_idle(tree, transcript))

    assert result.exit_code == 2
    assert "CHANGES.md" in result.output


def test_idle_without_teammate_transcript_judges_the_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the teammate's transcript cannot be found, fall back to the old
    behaviour: every changed .md in the payload cwd's tree."""
    tree = tmp_path / "session-repo"
    _init_repo(tree)
    (tree / "notes.md").write_text("Later" + chr(0x2026) + "\n", encoding="utf-8")
    transcript = _teammate_session(tmp_path)
    _patch_config(monkeypatch, [])

    result = runner.invoke(
        _mod.app,
        ["idle"],
        input=_teammate_idle(tree, transcript, agent_id="anobody-ffffffffffffffff"),
    )

    assert result.exit_code == 2
    assert "notes.md" in result.output


def test_security_checks_still_cover_the_whole_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the retry-able encoding check is narrowed: a .env anywhere in the
    tree still hard-stops, because Bash-created files never appear in the
    transcript's Edit/Write calls."""
    tree = tmp_path / "session-repo"
    _init_repo(tree)
    (tree / ".env").write_text("SECRET=x\n", encoding="utf-8")
    transcript = _teammate_session(tmp_path)
    _patch_config(monkeypatch, [])

    result = runner.invoke(_mod.app, ["idle"], input=_teammate_idle(tree, transcript))

    assert result.exit_code == 0
    assert json.loads(result.stdout)["continue"] is False
