"""Tests for instructions-guard.py -- InstructionsLoaded hook."""

from __future__ import annotations

import importlib
from pathlib import Path

# instructions-guard.py uses a hyphen, so we use importlib to load it.
_mod = importlib.import_module("instructions-guard")
validate_file = _mod.validate_file


class TestValidateFile:
    """Tests for the validate_file() core function."""

    def test_clean_file_no_warnings(self, tmp_path: Path) -> None:
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Clean file\nAll ASCII content here.\n", encoding="utf-8")
        warnings = validate_file(f)
        assert warnings == []

    def test_detects_smart_quotes(self, tmp_path: Path) -> None:
        f = tmp_path / "CLAUDE.md"
        # U+201C = left double quotation mark
        f.write_text("This has \u201csmart quotes\u201d in it.\n", encoding="utf-8")
        warnings = validate_file(f)
        assert len(warnings) == 1
        assert "encoding" in warnings[0].lower() or "utf" in warnings[0].lower() or "windows" in warnings[0].lower()

    def test_detects_placeholder_markers(self, tmp_path: Path) -> None:
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Title\nSome [PLACEHOLDER] text.\n", encoding="utf-8")
        warnings = validate_file(f)
        assert len(warnings) == 1
        assert "placeholder" in warnings[0].lower()

    def test_no_placeholder_check_when_disabled(self, tmp_path: Path) -> None:
        f = tmp_path / "CLAUDE.md"
        f.write_text("# Title\nSome [PLACEHOLDER] text.\n", encoding="utf-8")
        warnings = validate_file(f, placeholder_check=False)
        assert len(warnings) == 0

    def test_missing_file_no_crash(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.md"
        warnings = validate_file(missing)
        assert warnings == []
