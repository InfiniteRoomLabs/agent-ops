"""Tests for the summon validate subcommand."""

from __future__ import annotations

import textwrap
from pathlib import Path

from conftest import run_summon


def test_validate_valid_agent(agent_ops_root):
    """A well-formed agent file passes validation."""
    agent_path = agent_ops_root / "plugins" / "core" / "agents" / "alpha-agent.md"
    data, rc = run_summon("validate", str(agent_path), agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["valid"] is True
    assert data["errors"] == []


def test_validate_missing_description(tmp_path):
    """Agent without description field in frontmatter fails validation."""
    bad_agent = tmp_path / "bad-agent.md"
    bad_agent.write_text(textwrap.dedent("""\
        ---
        model: sonnet
        ---

        Some body content here.
    """), encoding="utf-8")
    data, rc = run_summon("validate", str(bad_agent))
    assert rc == 0
    assert data["valid"] is False
    assert any("description" in e.lower() for e in data["errors"])


def test_validate_no_frontmatter(tmp_path):
    """Agent file without frontmatter fails validation."""
    no_fm = tmp_path / "no-frontmatter.md"
    no_fm.write_text("# Just a heading\n\nSome text.\n", encoding="utf-8")
    data, rc = run_summon("validate", str(no_fm))
    assert rc == 0
    assert data["valid"] is False
    assert any("frontmatter" in e.lower() for e in data["errors"])


def test_validate_empty_body(tmp_path):
    """Agent file with frontmatter but empty body fails validation."""
    empty_body = tmp_path / "empty-body.md"
    empty_body.write_text(textwrap.dedent("""\
        ---
        description: Has frontmatter but no body
        ---
    """), encoding="utf-8")
    data, rc = run_summon("validate", str(empty_body))
    assert rc == 0
    assert data["valid"] is False
    assert any("body" in e.lower() for e in data["errors"])


def test_validate_nonexistent_file(tmp_path):
    """Nonexistent file path fails validation."""
    fake_path = tmp_path / "does-not-exist.md"
    data, rc = run_summon("validate", str(fake_path))
    assert rc == 0
    assert data["valid"] is False
    assert any("exist" in e.lower() for e in data["errors"])
