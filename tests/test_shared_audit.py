"""Tests for _shared.audit module."""
from __future__ import annotations

import json
from pathlib import Path

from _shared.audit import write_audit_entry


def test_write_audit_entry_creates_jsonl(tmp_path: Path) -> None:
    """Writing an entry creates a .jsonl file with valid JSON."""
    write_audit_entry(tmp_path, "test-log", {"action": "test"})
    log_file = tmp_path / "test-log.jsonl"
    assert log_file.exists()
    data = json.loads(log_file.read_text().strip())
    assert data["action"] == "test"


def test_write_audit_entry_appends(tmp_path: Path) -> None:
    """Writing two entries produces two lines."""
    write_audit_entry(tmp_path, "test-log", {"n": 1})
    write_audit_entry(tmp_path, "test-log", {"n": 2})
    lines = (tmp_path / "test-log.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["n"] == 1
    assert json.loads(lines[1])["n"] == 2


def test_write_audit_entry_adds_timestamp(tmp_path: Path) -> None:
    """Auto-timestamp is added when add_timestamp=True (default)."""
    write_audit_entry(tmp_path, "test-log", {"action": "test"})
    data = json.loads((tmp_path / "test-log.jsonl").read_text().strip())
    assert "timestamp" in data


def test_write_audit_entry_preserves_existing_timestamp(tmp_path: Path) -> None:
    """Existing timestamp in the entry is not overwritten."""
    write_audit_entry(
        tmp_path, "test-log", {"timestamp": "2025-01-01T00:00:00Z", "action": "test"}
    )
    data = json.loads((tmp_path / "test-log.jsonl").read_text().strip())
    assert data["timestamp"] == "2025-01-01T00:00:00Z"
