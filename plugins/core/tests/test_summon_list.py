"""Tests for the summon list subcommand."""

from __future__ import annotations

from conftest import run_summon


def test_list_returns_all_agents(agent_ops_root):
    """List returns all 3 agents from the test registry."""
    data, rc = run_summon("list", agent_ops_root=agent_ops_root)
    assert rc == 0
    names = [a["name"] for a in data["agents"]]
    assert "alpha-agent" in names
    assert "beta-agent" in names
    assert "gamma-agent" in names


def test_list_namespace_filter(agent_ops_root):
    """--namespace engineering returns only engineering agents."""
    data, rc = run_summon("list", "--namespace", "engineering", agent_ops_root=agent_ops_root)
    assert rc == 0
    names = [a["name"] for a in data["agents"]]
    assert "beta-agent" in names
    assert "gamma-agent" in names
    assert "alpha-agent" not in names


def test_list_namespace_core(agent_ops_root):
    """--namespace core returns only core agents."""
    data, rc = run_summon("list", "--namespace", "core", agent_ops_root=agent_ops_root)
    assert rc == 0
    names = [a["name"] for a in data["agents"]]
    assert names == ["alpha-agent"]


def test_list_includes_metadata(agent_ops_root):
    """List includes description, model, and color from frontmatter."""
    data, rc = run_summon("list", agent_ops_root=agent_ops_root)
    assert rc == 0
    beta = next(a for a in data["agents"] if a["name"] == "beta-agent")
    assert beta["model"] == "opus"
    assert beta["color"] == "green"
    assert "engineering" in beta["description"].lower() or len(beta["description"]) > 0


def test_list_filesystem_fallback(agent_ops_root):
    """When registry.yaml is missing, list falls back to filesystem scan."""
    import os
    os.remove(agent_ops_root / "registry.yaml")
    data, rc = run_summon("list", agent_ops_root=agent_ops_root)
    assert rc == 0
    names = [a["name"] for a in data["agents"]]
    # Should still find agents via filesystem
    assert len(names) >= 3


def test_list_empty_namespace(agent_ops_root):
    """Nonexistent namespace returns empty list."""
    data, rc = run_summon("list", "--namespace", "nonexistent", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert data["agents"] == []
