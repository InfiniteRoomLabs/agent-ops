"""Shared Pydantic models for Claude Code Bash hook payloads.

Five guards (auto-tag, changelog-guard, commit_guard, test-coverage-guard,
version_guard) parse the same PreToolUse/PostToolUse JSON shape for Bash
commands. They share this model instead of redefining it; a guard that needs
extra fields (e.g. auto-tag's PostToolUse ``tool_response``) subclasses it.
"""
from __future__ import annotations

from pydantic import BaseModel


class BashToolInput(BaseModel):
    command: str = ""


class BashHookPayload(BaseModel):
    """PreToolUse/PostToolUse payload for a Bash command."""

    tool_name: str = ""
    tool_input: BashToolInput = BashToolInput()
    cwd: str = ""
