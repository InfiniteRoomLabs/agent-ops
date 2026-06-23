"""Tests for the shared Bash hook payload models."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from _shared.hook_payload import BashHookPayload, BashToolInput  # noqa: E402


def test_parses_full_payload():
    payload = BashHookPayload.model_validate_json(
        '{"tool_name": "Bash", "tool_input": {"command": "git commit"}, "cwd": "/repo"}'
    )
    assert payload.tool_name == "Bash"
    assert payload.tool_input.command == "git commit"
    assert payload.cwd == "/repo"


def test_defaults_on_empty_object():
    payload = BashHookPayload.model_validate_json("{}")
    assert payload.tool_name == ""
    assert payload.tool_input.command == ""
    assert payload.cwd == ""


def test_unknown_fields_ignored():
    payload = BashHookPayload.model_validate_json(
        '{"tool_input": {"command": "ls"}, "extra": 123}'
    )
    assert payload.tool_input.command == "ls"


def test_subclass_adds_field():
    from typing import Any

    class WithResponse(BashHookPayload):
        tool_response: Any = None

    payload = WithResponse.model_validate_json(
        '{"tool_input": {"command": "x"}, "tool_response": {"ok": true}}'
    )
    assert payload.tool_input.command == "x"
    assert payload.tool_response == {"ok": True}


def test_tool_input_default_is_isolated():
    a = BashToolInput()
    assert a.command == ""
