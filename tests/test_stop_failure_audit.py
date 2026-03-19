"""Tests for stop-failure-audit write_failure_audit() function."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

# stop-failure-audit.py uses a hyphen, so we use importlib to load it.
_mod = importlib.import_module("stop-failure-audit")
write_failure_audit = _mod.write_failure_audit


class TestWriteFailureAudit:
    """Tests for the core write_failure_audit logic."""

    def test_write_audit_entry(self, tmp_path: Path) -> None:

        write_failure_audit(
            audit_dir=tmp_path,
            error="session_crashed",
            error_details="Unexpected EOF while parsing",
            session_id="sess-abc-123",
            cwd="/home/user/projects/myapp",
            agent_name="DevOps Lead",
        )

        log_file = tmp_path / "stop-failures.jsonl"
        assert log_file.exists()

        entry = json.loads(log_file.read_text().strip())
        assert entry["error"] == "session_crashed"
        assert entry["error_details"] == "Unexpected EOF while parsing"
        assert entry["session_id"] == "sess-abc-123"
        assert entry["cwd"] == "/home/user/projects/myapp"
        assert entry["agent_name"] == "DevOps Lead"
        assert "timestamp" in entry

    def test_write_audit_appends(self, tmp_path: Path) -> None:
        write_failure_audit(
            audit_dir=tmp_path,
            error="error_one",
            error_details="First failure",
            session_id="sess-001",
            cwd="/home/user/project-a",
            agent_name="Agent A",
        )
        write_failure_audit(
            audit_dir=tmp_path,
            error="error_two",
            error_details="Second failure",
            session_id="sess-002",
            cwd="/home/user/project-b",
            agent_name="Agent B",
        )

        log_file = tmp_path / "stop-failures.jsonl"
        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 2

        first = json.loads(lines[0])
        second = json.loads(lines[1])
        assert first["error"] == "error_one"
        assert second["error"] == "error_two"

    def test_write_audit_no_agent(self, tmp_path: Path) -> None:
        write_failure_audit(
            audit_dir=tmp_path,
            error="orphan_crash",
            error_details="No agent was loaded",
            session_id="sess-orphan",
            cwd="/tmp/scratch",
            agent_name=None,
        )

        log_file = tmp_path / "stop-failures.jsonl"
        entry = json.loads(log_file.read_text().strip())
        assert entry["agent_name"] is None
