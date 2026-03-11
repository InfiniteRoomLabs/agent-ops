"""Tests for the summon list subcommand."""

from __future__ import annotations

from conftest import run_summon


def test_list_returns_json(agent_ops_root):
    data, rc = run_summon("list", agent_ops_root=agent_ops_root)
    assert rc == 0
    assert "agents" in data
