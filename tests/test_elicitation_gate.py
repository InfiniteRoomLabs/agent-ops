"""Tests for elicitation-gate.py -- Elicitation and ElicitationResult hooks."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

# elicitation-gate.py uses a hyphen, so we use importlib to load it.
_mod = importlib.import_module("elicitation-gate")
check_elicitation = _mod.check_elicitation
write_elicitation_audit = _mod.write_elicitation_audit


class TestCheckElicitation:
    """Tests for the check_elicitation() core function."""

    def test_no_block_patterns_allows(self) -> None:
        result = check_elicitation(
            server_name="some-mcp-server",
            request_type="tool_call",
            parameters={"tool": "delete_zone"},
            block_patterns=[],
        )
        assert result["blocked"] is False
        assert result["matched_pattern"] == ""

    def test_block_pattern_matches(self) -> None:
        result = check_elicitation(
            server_name="some-mcp-server",
            request_type="tool_call",
            parameters={"tool": "delete_zone"},
            block_patterns=["delete_.*"],
        )
        assert result["blocked"] is True
        assert result["matched_pattern"] == "delete_.*"

    def test_block_pattern_no_match(self) -> None:
        result = check_elicitation(
            server_name="some-mcp-server",
            request_type="tool_call",
            parameters={"tool": "list_zones"},
            block_patterns=["delete_.*"],
        )
        assert result["blocked"] is False
        assert result["matched_pattern"] == ""


class TestWriteElicitationAudit:
    """Tests for the write_elicitation_audit() function."""

    def test_audit_entry_written(self, tmp_path: Path) -> None:
        audit_dir = tmp_path / "audit"

        write_elicitation_audit(
            audit_dir=audit_dir,
            event_type="elicitation_request",
            server_name="test-server",
            details={"request_type": "tool_call", "parameters": {"tool": "list_zones"}},
        )

        log_file = audit_dir / "elicitation-events.jsonl"
        assert log_file.exists()

        lines = log_file.read_text().strip().splitlines()
        assert len(lines) == 1

        entry = json.loads(lines[0])
        assert entry["server_name"] == "test-server"
        assert entry["event_type"] == "elicitation_request"
        assert "timestamp" in entry
