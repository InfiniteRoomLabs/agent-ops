"""Tests for summon.py -- session state lifecycle (create/check/clean)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
from typer.testing import CliRunner

import summon

runner = CliRunner()


def _create(state_dir: Path) -> object:
    """Invoke `state create` against an isolated state dir."""
    return runner.invoke(
        summon.app,
        [
            "--state-dir", str(state_dir),
            "state", "create",
            "--agent", "devops-cto",
            "--division", "engineering",
            "--source", "/fake/path.md",
        ],
    )


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    return tmp_path / "summon-state"


# ---------------------------------------------------------------------------
# session_id sourcing
# ---------------------------------------------------------------------------


def test_create_uses_env_session_id(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """session_id comes from CLAUDE_SESSION_ID when set (per the implementation
    plan) -- a random UUID would make every state file instantly stale."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "live-session-123")
    result = _create(state_dir)
    assert result.exit_code == 0

    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
    assert state["session_id"] == "live-session-123"


def test_create_falls_back_to_random_uuid(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without CLAUDE_SESSION_ID, session_id is a fresh UUID."""
    monkeypatch.delenv("CLAUDE_SESSION_ID", raising=False)
    result = _create(state_dir)
    assert result.exit_code == 0

    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
    uuid.UUID(state["session_id"])  # raises if not a valid UUID


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------


def test_check_not_stale_for_same_session(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """State created in the live session is NOT stale at check time."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "session-abc")
    _create(state_dir)

    result = runner.invoke(
        summon.app, ["--state-dir", str(state_dir), "state", "check"]
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["active"] is True
    assert data["stale"] is False


def test_check_stale_for_different_session(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_SESSION_ID", "session-abc")
    _create(state_dir)

    monkeypatch.setenv("CLAUDE_SESSION_ID", "a-completely-different-session")
    result = runner.invoke(
        summon.app, ["--state-dir", str(state_dir), "state", "check"]
    )
    data = json.loads(result.stdout)
    assert data["stale"] is True


def test_clean_if_stale_keeps_live_session_state(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SessionStart clean must not delete the live session's persona."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "session-abc")
    _create(state_dir)

    result = runner.invoke(
        summon.app, ["--state-dir", str(state_dir), "state", "clean", "--if-stale"]
    )
    assert result.exit_code == 0
    assert json.loads(result.stdout)["cleaned"] is False
    assert (state_dir / "state.json").exists()


def test_clean_if_stale_removes_other_session_state(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("CLAUDE_SESSION_ID", "session-abc")
    _create(state_dir)

    monkeypatch.setenv("CLAUDE_SESSION_ID", "another-session")
    result = runner.invoke(
        summon.app, ["--state-dir", str(state_dir), "state", "clean", "--if-stale"]
    )
    assert json.loads(result.stdout)["cleaned"] is True
    assert not (state_dir / "state.json").exists()


# ---------------------------------------------------------------------------
# Atomic state write
# ---------------------------------------------------------------------------


def test_create_leaves_no_partial_or_tmp_file(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The state write is atomic: only a complete state.json remains."""
    monkeypatch.setenv("CLAUDE_SESSION_ID", "session-abc")
    result = _create(state_dir)
    assert result.exit_code == 0

    leftovers = [p.name for p in state_dir.iterdir() if p.name != "state.json"]
    assert leftovers == []
    # The surviving file is complete, parseable state
    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))
    assert state["active_agent"] == "devops-cto"


def test_atomic_write_replaces_existing_content(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    target.write_text('{"old": true}', encoding="utf-8")
    summon._atomic_write_text(target, '{"new": true}')
    assert json.loads(target.read_text(encoding="utf-8")) == {"new": True}
    assert list(tmp_path.iterdir()) == [target]


# ---------------------------------------------------------------------------
# State dir keying
# ---------------------------------------------------------------------------


def test_get_state_dir_prefers_claude_project_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """State is keyed to CLAUDE_PROJECT_DIR (the session's project root), not
    the live process cwd, so subshell/worktree invocations share one slug."""
    monkeypatch.setattr(summon, "_state_dir_override", None)
    project = tmp_path / "my-project"
    project.mkdir()
    other = tmp_path / "somewhere-else"
    other.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(project))
    monkeypatch.chdir(other)

    sd = summon.get_state_dir()
    expected_slug = str(project.resolve()).replace("/", "-")
    assert expected_slug in str(sd)
    assert str(other.resolve()).replace("/", "-") not in str(sd)


def test_get_state_dir_falls_back_to_cwd(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(summon, "_state_dir_override", None)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    sd = summon.get_state_dir()
    assert str(tmp_path.resolve()).replace("/", "-") in str(sd)
