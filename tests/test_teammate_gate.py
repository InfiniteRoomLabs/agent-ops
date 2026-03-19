"""Tests for teammate-gate.py."""

from __future__ import annotations

import importlib
from pathlib import Path

# teammate-gate.py uses a hyphen, so we use importlib to load it.
_mod = importlib.import_module("teammate-gate")
check_encoding = _mod.check_encoding
check_env_files = _mod.check_env_files
check_agent_dirs = _mod.check_agent_dirs
classify_violations = _mod.classify_violations


def test_encoding_check_finds_smart_quotes(tmp_path: Path) -> None:
    """Markdown file containing U+201C left double quotation mark triggers a violation."""
    md = tmp_path / "doc.md"
    md.write_text("Hello \u201cworld\u201d\n", encoding="utf-8")
    violations = check_encoding([md])
    assert len(violations) == 1
    assert violations[0]["type"] == "encoding"
    assert violations[0]["severity"] == "fixable"


def test_encoding_check_clean_file(tmp_path: Path) -> None:
    """A markdown file with only ASCII content produces no violations."""
    md = tmp_path / "clean.md"
    md.write_text("# Title\n\nJust plain ASCII text.\n", encoding="utf-8")
    violations = check_encoding([md])
    assert len(violations) == 0


def test_env_file_check_finds_env(tmp_path: Path) -> None:
    """A .env file path triggers a security violation."""
    env = tmp_path / ".env"
    violations = check_env_files([env])
    assert len(violations) == 1
    assert violations[0]["type"] == "env_files"
    assert violations[0]["severity"] == "security"


def test_agent_dir_check_finds_claude_dir(tmp_path: Path) -> None:
    """A file inside .claude/ triggers a security violation."""
    agent_file = tmp_path / ".claude" / "settings.json"
    violations = check_agent_dirs([agent_file])
    assert len(violations) == 1
    assert violations[0]["type"] == "agent_dirs"
    assert violations[0]["severity"] == "security"


def test_classify_violations() -> None:
    """Mixed violations split correctly into fixable and security buckets."""
    violations = [
        {"type": "encoding", "file": "a.md", "message": "smart quotes", "severity": "fixable"},
        {"type": "env_files", "file": ".env", "message": "env file", "severity": "security"},
        {"type": "agent_dirs", "file": ".claude/x", "message": "agent dir", "severity": "security"},
        {"type": "encoding", "file": "b.md", "message": "em dash", "severity": "fixable"},
    ]
    fixable, security = classify_violations(violations)
    assert len(fixable) == 2
    assert len(security) == 2
    assert all(v["severity"] == "fixable" for v in fixable)
    assert all(v["severity"] == "security" for v in security)
