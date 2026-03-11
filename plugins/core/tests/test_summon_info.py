"""Tests for the summon info subcommand."""

from __future__ import annotations

from conftest import run_summon


def test_info_returns_first_paragraph(agent_ops_root):
    """Info returns only the first paragraph, not the full body."""
    data, rc = run_summon("info", "alpha-agent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["found"] is True
    body = data["agent"]["body"]
    # First paragraph is the description line after the heading
    assert "A test agent used in the core plugin for unit testing." in body
    # Should NOT contain the Iron Laws section
    assert "Iron Laws" not in body


def test_info_not_found(agent_ops_root):
    """Info for unknown agent returns found=false."""
    data, rc = run_summon("info", "nonexistent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["found"] is False


def test_info_includes_frontmatter_metadata(agent_ops_root):
    """Info result includes frontmatter fields like model and description."""
    data, rc = run_summon("info", "gamma-agent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["found"] is True
    agent = data["agent"]
    assert agent["model"] == "haiku"
    assert agent["color"] == "purple"
    assert agent["description"] == "Gamma test agent for research tasks"
