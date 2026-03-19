"""Tests for postcompact-recovery check_compaction() function."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

# Import the hyphenated script via importlib so tests can reference it cleanly.
_scripts_dir = str(Path(__file__).resolve().parent.parent / "scripts")
if _scripts_dir not in sys.path:
    sys.path.insert(0, _scripts_dir)
_mod = importlib.import_module("postcompact-recovery")
check_compaction = _mod.check_compaction


class TestCheckCompaction:
    """Tests for the core check_compaction logic."""

    def test_no_reinject_strings_no_warning(self) -> None:
        result = check_compaction(
            compact_summary="Some compacted summary text.",
            reinject_strings=[],
            agent_name=None,
        )
        assert result["warnings"] == []

    def test_missing_reinject_string_produces_warning(self) -> None:
        result = check_compaction(
            compact_summary="The summary mentions nothing relevant.",
            reinject_strings=["CHANGELOG guard", "version enforcement"],
            agent_name=None,
        )
        assert len(result["warnings"]) == 2

    def test_present_reinject_string_no_warning(self) -> None:
        result = check_compaction(
            compact_summary="Remember to run the CHANGELOG guard before committing.",
            reinject_strings=["CHANGELOG guard"],
            agent_name=None,
        )
        assert len(result["warnings"]) == 0

    def test_agent_name_missing_from_summary(self) -> None:
        result = check_compaction(
            compact_summary="Working on hook enforcement tasks.",
            reinject_strings=[],
            agent_name="DevOps Lead",
        )
        assert len(result["warnings"]) == 1

    def test_agent_name_present_in_summary(self) -> None:
        result = check_compaction(
            compact_summary="Operating as DevOps Lead on infrastructure work.",
            reinject_strings=[],
            agent_name="DevOps Lead",
        )
        assert len(result["warnings"]) == 0
