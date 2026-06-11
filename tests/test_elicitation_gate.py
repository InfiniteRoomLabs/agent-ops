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


class TestMalformedPayload:
    """Hook entrypoints must honor their exit-0 contract on unparseable stdin."""

    @staticmethod
    def _patch_config(monkeypatch, block_patterns):
        def fake_resolve_typed(model, namespace, **kw):
            return _mod.McpConfig(
                audit_elicitations=False, block_patterns=block_patterns
            )

        monkeypatch.setattr(_mod, "resolve_typed", fake_resolve_typed)

    def test_request_malformed_no_patterns_exits_clean(self, monkeypatch) -> None:
        from typer.testing import CliRunner

        self._patch_config(monkeypatch, [])
        result = CliRunner().invoke(_mod.app, ["request"], input="not json")
        assert result.exit_code == 0
        assert "decline" not in result.stdout

    def test_request_malformed_with_patterns_declines(self, monkeypatch) -> None:
        """With blocking configured, an unparseable payload fails CLOSED."""
        from typer.testing import CliRunner

        self._patch_config(monkeypatch, ["delete_.*"])
        result = CliRunner().invoke(_mod.app, ["request"], input="not json")
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["hookSpecificOutput"]["action"] == "decline"

    def test_result_malformed_exits_clean(self, monkeypatch) -> None:
        from typer.testing import CliRunner

        self._patch_config(monkeypatch, [])
        result = CliRunner().invoke(_mod.app, ["result"], input="{broken")
        assert result.exit_code == 0
