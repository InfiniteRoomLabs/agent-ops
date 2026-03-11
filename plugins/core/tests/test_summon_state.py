"""Tests for the summon state subcommands."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

from conftest import run_summon, SUMMON_SCRIPT


def test_state_check_no_state(state_dir):
    """Check with no existing state returns active=false."""
    data, rc = run_summon("state", "check", state_dir=state_dir)
    assert rc == 0
    assert data["active"] is False


def test_state_create_then_check(state_dir, agent_ops_root):
    """Create state then check it returns active=true with correct data."""
    data, rc = run_summon(
        "state", "create",
        "--agent", "alpha-agent",
        "--plugin", "core",
        "--source", "/tmp/fake/alpha-agent.md",
        state_dir=state_dir,
        agent_ops_root=agent_ops_root,
    )
    assert rc == 0
    assert data["created"] is True
    assert "path" in data

    # Now check
    data, rc = run_summon("state", "check", state_dir=state_dir)
    assert rc == 0
    assert data["active"] is True
    assert data["agent"]["active_agent"] == "alpha-agent"
    assert data["agent"]["plugin"] == "core"
    assert data["stale"] is False


def test_state_delete(state_dir, agent_ops_root):
    """Delete removes existing state."""
    # Create first
    run_summon(
        "state", "create",
        "--agent", "alpha-agent",
        "--plugin", "core",
        "--source", "/tmp/fake/alpha-agent.md",
        state_dir=state_dir,
        agent_ops_root=agent_ops_root,
    )
    # Delete
    data, rc = run_summon("state", "delete", state_dir=state_dir)
    assert rc == 0
    assert data["deleted"] is True

    # Verify gone
    data, rc = run_summon("state", "check", state_dir=state_dir)
    assert rc == 0
    assert data["active"] is False


def test_state_delete_no_state(state_dir):
    """Delete when no state exists returns deleted=false."""
    data, rc = run_summon("state", "delete", state_dir=state_dir)
    assert rc == 0
    assert data["deleted"] is False


def test_state_clean_removes_stale(state_dir):
    """Clean with --if-stale removes state older than 24 hours."""
    state_file = state_dir / "state.json"
    old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
    state_file.write_text(json.dumps({
        "active_agent": "old-agent",
        "plugin": "core",
        "source_file": "/tmp/fake.md",
        "loaded_at": old_time,
        "session_id": "test-session-id",
    }), encoding="utf-8")

    data, rc = run_summon("state", "clean", "--if-stale", state_dir=state_dir)
    assert rc == 0
    assert data["cleaned"] is True
    assert not state_file.exists()


def test_state_clean_preserves_fresh(state_dir):
    """Clean with --if-stale preserves state younger than 24 hours."""
    state_file = state_dir / "state.json"
    fresh_time = datetime.now(timezone.utc).isoformat()
    state_file.write_text(json.dumps({
        "active_agent": "fresh-agent",
        "plugin": "core",
        "source_file": "/tmp/fake.md",
        "loaded_at": fresh_time,
        "session_id": "test-session-id",
    }), encoding="utf-8")

    data, rc = run_summon("state", "clean", "--if-stale", state_dir=state_dir)
    assert rc == 0
    assert data["cleaned"] is False
    assert state_file.exists()


def test_state_clean_without_flag_always_removes(state_dir):
    """Clean without --if-stale always removes state."""
    state_file = state_dir / "state.json"
    fresh_time = datetime.now(timezone.utc).isoformat()
    state_file.write_text(json.dumps({
        "active_agent": "fresh-agent",
        "plugin": "core",
        "source_file": "/tmp/fake.md",
        "loaded_at": fresh_time,
        "session_id": "test-session-id",
    }), encoding="utf-8")

    data, rc = run_summon("state", "clean", state_dir=state_dir)
    assert rc == 0
    assert data["cleaned"] is True
    assert not state_file.exists()


def test_state_reminder_active(state_dir, agent_ops_root):
    """Reminder returns persona text when an agent is active."""
    run_summon(
        "state", "create",
        "--agent", "alpha-agent",
        "--plugin", "core",
        "--source", "/tmp/fake/alpha-agent.md",
        state_dir=state_dir,
        agent_ops_root=agent_ops_root,
    )

    data, rc = run_summon("state", "reminder", state_dir=state_dir)
    assert rc == 0
    assert data["active"] is True
    assert "alpha-agent" in data["reminder"]
    assert "AGENT SESSION REMINDER" in data["reminder"]


def test_state_reminder_no_state(state_dir):
    """Reminder returns empty when no agent is loaded."""
    data, rc = run_summon("state", "reminder", state_dir=state_dir)
    assert rc == 0
    assert data["active"] is False
    assert data["reminder"] == ""


def test_state_clean_session_id_mismatch(state_dir):
    """Clean with --if-stale removes fresh state when session ID mismatches."""
    state_file = state_dir / "state.json"
    fresh_time = datetime.now(timezone.utc).isoformat()
    state_file.write_text(json.dumps({
        "active_agent": "old-session-agent",
        "plugin": "core",
        "source_file": "/tmp/fake.md",
        "loaded_at": fresh_time,
        "session_id": "old-session-id",
    }), encoding="utf-8")

    # Run with CLAUDE_SESSION_ID set to a different value
    env = os.environ.copy()
    env["CLAUDE_SESSION_ID"] = "new-session-id"
    result = subprocess.run(
        ["uv", "run", str(SUMMON_SCRIPT), "--state-dir", str(state_dir),
         "state", "clean", "--if-stale"],
        capture_output=True, text=True, timeout=60, env=env,
    )
    data = json.loads(result.stdout)
    assert result.returncode == 0
    assert data["cleaned"] is True
    assert not state_file.exists()


def test_state_clean_session_id_match_preserves(state_dir):
    """Clean with --if-stale preserves fresh state when session ID matches."""
    state_file = state_dir / "state.json"
    fresh_time = datetime.now(timezone.utc).isoformat()
    state_file.write_text(json.dumps({
        "active_agent": "same-session-agent",
        "plugin": "core",
        "source_file": "/tmp/fake.md",
        "loaded_at": fresh_time,
        "session_id": "matching-session-id",
    }), encoding="utf-8")

    # Run with matching CLAUDE_SESSION_ID
    env = os.environ.copy()
    env["CLAUDE_SESSION_ID"] = "matching-session-id"
    result = subprocess.run(
        ["uv", "run", str(SUMMON_SCRIPT), "--state-dir", str(state_dir),
         "state", "clean", "--if-stale"],
        capture_output=True, text=True, timeout=60, env=env,
    )
    data = json.loads(result.stdout)
    assert result.returncode == 0
    assert data["cleaned"] is False
    assert state_file.exists()
