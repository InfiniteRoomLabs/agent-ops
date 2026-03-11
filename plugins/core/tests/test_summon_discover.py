"""Tests for the summon discover subcommand."""

from __future__ import annotations

import os

from conftest import run_summon


def test_discover_exact_match(agent_ops_root):
    """Exact name match returns found=true with agent detail."""
    data, rc = run_summon("discover", "alpha-agent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["found"] is True
    assert data["agent"]["name"] == "alpha-agent"


def test_discover_case_insensitive(agent_ops_root):
    """Discovery is case-insensitive."""
    data, rc = run_summon("discover", "Alpha-Agent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["found"] is True
    assert data["agent"]["name"] == "alpha-agent"


def test_discover_substring_match(agent_ops_root):
    """Substring match returns the agent when there is exactly one."""
    data, rc = run_summon("discover", "alpha", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["found"] is True
    assert data["agent"]["name"] == "alpha-agent"


def test_discover_multiple_matches(agent_ops_root):
    """Ambiguous substring returns found=false with matches list."""
    # "agent" matches all three: alpha-agent, beta-agent, gamma-agent
    data, rc = run_summon("discover", "agent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["found"] is False
    assert len(data["matches"]) == 3


def test_discover_namespace_filter(agent_ops_root):
    """--namespace limits discovery to a specific plugin."""
    data, rc = run_summon(
        "discover", "beta-agent", "--namespace", "engineering",
        agent_ops_root=agent_ops_root,
    )
    assert rc == 0
    assert data["found"] is True
    assert data["agent"]["plugin"] == "engineering"


def test_discover_wrong_namespace(agent_ops_root):
    """Agent exists but not in the requested namespace -> not found."""
    data, rc = run_summon(
        "discover", "alpha-agent", "--namespace", "engineering",
        agent_ops_root=agent_ops_root,
    )
    assert rc == 0
    assert data["found"] is False
    assert data["matches"] == []


def test_discover_not_found(agent_ops_root):
    """Completely unknown name returns found=false, empty matches."""
    data, rc = run_summon("discover", "nonexistent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["found"] is False
    assert data["matches"] == []


def test_discover_includes_body(agent_ops_root):
    """Discovered agent includes full body text."""
    data, rc = run_summon("discover", "alpha-agent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert "Iron Laws" in data["agent"]["body"]
    assert "NEVER do anything unexpected" in data["agent"]["body"]


def test_discover_includes_frontmatter(agent_ops_root):
    """Discovered agent includes frontmatter fields."""
    data, rc = run_summon("discover", "beta-agent", agent_ops_root=agent_ops_root)
    assert rc == 0
    agent = data["agent"]
    assert agent["model"] == "opus"
    assert agent["color"] == "green"
    assert agent["description"] == "Beta test agent for engineering workflows"


def test_discover_filesystem_fallback(agent_ops_root):
    """When registry has no agents section, discovery falls back to filesystem."""
    os.remove(agent_ops_root / "registry.yaml")
    data, rc = run_summon("discover", "gamma-agent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["found"] is True
    assert data["agent"]["name"] == "gamma-agent"
