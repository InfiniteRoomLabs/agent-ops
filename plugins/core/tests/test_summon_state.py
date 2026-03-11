"""Tests for the summon state subcommands."""

from __future__ import annotations

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

from conftest import run_summon


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
