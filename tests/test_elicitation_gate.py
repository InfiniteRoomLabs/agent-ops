"""Tests for elicitation-gate.py -- Elicitation and ElicitationResult hooks."""

from __future__ import annotations

import importlib
import json
from pathlib import Path

import pytest

# elicitation-gate.py uses a hyphen, so we use importlib to load it.
_mod = importlib.import_module("elicitation-gate")
check_elicitation = _mod.check_elicitation
write_elicitation_audit = _mod.write_elicitation_audit


def _common(event: str) -> dict:
    return {
        "session_id": "00000000-0000-4000-8000-000000000000",
        "transcript_path": "path/to/session.jsonl",
        "cwd": "path/to/project",
        "permission_mode": "default",
        "hook_event_name": event,
    }


def claude_code_elicitation(message: str, server: str = "some-mcp-server") -> dict:
    """Elicitation stdin exactly as Claude Code sends it: the common fields
    plus mcp_server_name, message and the optional mode, url, elicitation_id
    and requested_schema. There is no server_name, request_type or
    parameters. Schema per the hooks reference and the 2.1.329 input schema."""
    return {
        **_common("Elicitation"),
        "mcp_server_name": server,
        "message": message,
        "mode": "form",
        "elicitation_id": "elicit-1",
        "requested_schema": {
            "type": "object",
            "properties": {"confirm": {"type": "boolean"}},
        },
    }


def claude_code_elicitation_result(action: str, content: dict) -> dict:
    """ElicitationResult stdin as Claude Code sends it: mcp_server_name,
    action (accept | decline | cancel) and the optional elicitation_id,
    mode and content. There is no `result` field."""
    return {
        **_common("ElicitationResult"),
        "mcp_server_name": "some-mcp-server",
        "elicitation_id": "elicit-1",
        "mode": "form",
        "action": action,
        "content": content,
    }


class TestCheckElicitation:
    """Tests for the check_elicitation() core function."""

    def test_no_block_patterns_allows(self) -> None:
        result = check_elicitation(
            request={"mcp_server_name": "some-mcp-server", "message": "delete_zone?"},
            block_patterns=[],
        )
        assert result["blocked"] is False
        assert result["matched_pattern"] == ""

    def test_block_pattern_matches(self) -> None:
        result = check_elicitation(
            request={"mcp_server_name": "some-mcp-server", "message": "delete_zone?"},
            block_patterns=["delete_.*"],
        )
        assert result["blocked"] is True
        assert result["matched_pattern"] == "delete_.*"

    def test_block_pattern_no_match(self) -> None:
        result = check_elicitation(
            request={"mcp_server_name": "some-mcp-server", "message": "list_zones?"},
            block_patterns=["delete_.*"],
        )
        assert result["blocked"] is False
        assert result["matched_pattern"] == ""


class TestRealPayloads:
    """The entry points read the fields Claude Code actually sends."""

    @pytest.fixture()
    def audit(self, monkeypatch) -> list[dict]:
        events: list[dict] = []
        monkeypatch.setattr(_mod, "get_audit_dir", lambda *a, **kw: Path("unused"))
        monkeypatch.setattr(
            _mod, "write_audit_entry", lambda _dir, _name, entry: events.append(entry)
        )
        return events

    @staticmethod
    def _config(monkeypatch, block_patterns: list[str]) -> None:
        monkeypatch.setattr(
            _mod,
            "resolve_typed",
            lambda model, namespace, **kw: _mod.McpConfig(block_patterns=block_patterns),
        )

    @staticmethod
    def _run(command: str, payload: dict):
        from typer.testing import CliRunner

        return CliRunner().invoke(_mod.app, [command], input=json.dumps(payload))

    def test_pattern_matching_the_message_declines(self, monkeypatch, audit) -> None:
        self._config(monkeypatch, ["delete_.*"])
        result = self._run("request", claude_code_elicitation("Confirm delete_zone?"))
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["hookSpecificOutput"]["action"] == "decline"
        assert audit[-1]["event_type"] == "elicitation_blocked"

    def test_pattern_matching_the_server_declines(self, monkeypatch, audit) -> None:
        self._config(monkeypatch, ["risky-server"])
        result = self._run(
            "request", claude_code_elicitation("Pick a zone", server="risky-server")
        )
        assert result.exit_code == 0, result.output
        assert json.loads(result.stdout)["hookSpecificOutput"]["action"] == "decline"

    def test_pattern_does_not_match_common_fields(self, monkeypatch, audit) -> None:
        """Patterns see the request, not session plumbing such as cwd."""
        self._config(monkeypatch, ["path/to/project"])
        result = self._run("request", claude_code_elicitation("Pick a zone"))
        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == ""

    def test_request_audit_records_server_and_message(self, monkeypatch, audit) -> None:
        self._config(monkeypatch, [])
        result = self._run("request", claude_code_elicitation("Pick a zone"))
        assert result.exit_code == 0, result.output
        assert result.stdout.strip() == ""
        entry = audit[-1]
        assert entry["event_type"] == "elicitation_request"
        assert entry["server_name"] == "some-mcp-server"
        assert entry["message"] == "Pick a zone"

    def test_result_audit_records_action_and_field_names_only(
        self, monkeypatch, audit
    ) -> None:
        """What the user typed into the form is not written to the audit log;
        the action and the names of the submitted fields are."""
        self._config(monkeypatch, [])
        result = self._run(
            "result", claude_code_elicitation_result("accept", {"token": "s3cret"})
        )
        assert result.exit_code == 0, result.output
        entry = audit[-1]
        assert entry["event_type"] == "elicitation_result"
        assert entry["server_name"] == "some-mcp-server"
        assert entry["action"] == "accept"
        assert entry["content_fields"] == ["token"]
        assert "s3cret" not in json.dumps(entry)


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
