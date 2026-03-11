"""Shared pytest fixtures for SUMMON CLI tests."""

from __future__ import annotations

import json
import subprocess
import textwrap
from pathlib import Path

import pytest

SUMMON_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "summon.py"


# ---------------------------------------------------------------------------
# Test agent data
# ---------------------------------------------------------------------------

ALPHA_AGENT_MD = textwrap.dedent("""\
    ---
    description: Alpha test agent for core operations
    model: sonnet
    tools: Glob, Grep, Read
    color: blue
    tags:
      function: [engineering]
      scenario: [testing]
      custom: [alpha, unit-test]
    ---

    # Alpha Agent

    A test agent used in the core plugin for unit testing.

    ## Iron Laws

    - NEVER do anything unexpected.
    - ALWAYS return predictable results.
""")

BETA_AGENT_MD = textwrap.dedent("""\
    ---
    description: Beta test agent for engineering workflows
    model: opus
    tools: Glob, Grep, Read, Bash
    color: green
    tags:
      function: [engineering]
      scenario: [ci-cd, testing]
      custom: [beta, integration-test]
    ---

    # Beta Agent

    A test agent in the engineering plugin for integration testing.

    ## Iron Laws

    - NEVER modify production resources.
    - ALWAYS log actions taken.
""")

GAMMA_AGENT_MD = textwrap.dedent("""\
    ---
    description: Gamma test agent for research tasks
    model: haiku
    tools: Read, WebFetch
    color: purple
    tags:
      function: [research]
      scenario: [analysis]
      custom: [gamma, smoke-test]
    ---

    # Gamma Agent

    A test agent in the engineering plugin for research-adjacent tasks.

    ## Iron Laws

    - NEVER fabricate data.
    - ALWAYS cite sources.
""")

REGISTRY_YAML = textwrap.dedent("""\
    agents:
      alpha-agent:
        plugin: core
        path: plugins/core/agents/alpha-agent
        function: [engineering]
        scenario: [testing]
        status: active

      beta-agent:
        plugin: engineering
        path: plugins/engineering/agents/beta-agent
        function: [engineering]
        scenario: [ci-cd, testing]
        status: active

      gamma-agent:
        plugin: engineering
        path: plugins/engineering/agents/gamma-agent
        function: [research]
        scenario: [analysis]
        status: active
""")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def agent_ops_root(tmp_path: Path) -> Path:
    """Create a temporary agent-ops directory tree with test agents."""
    root = tmp_path / "agent-ops"
    root.mkdir()

    # Write registry
    (root / "registry.yaml").write_text(REGISTRY_YAML, encoding="utf-8")

    # Core plugin -- alpha agent
    core_agents = root / "plugins" / "core" / "agents"
    core_agents.mkdir(parents=True)
    (core_agents / "alpha-agent.md").write_text(ALPHA_AGENT_MD, encoding="utf-8")

    # Engineering plugin -- beta and gamma agents
    eng_agents = root / "plugins" / "engineering" / "agents"
    eng_agents.mkdir(parents=True)
    (eng_agents / "beta-agent.md").write_text(BETA_AGENT_MD, encoding="utf-8")
    (eng_agents / "gamma-agent.md").write_text(GAMMA_AGENT_MD, encoding="utf-8")

    return root


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    """Return an empty temporary directory for state tests."""
    d = tmp_path / "summon-state"
    d.mkdir()
    return d


def run_summon(
    *args: str,
    agent_ops_root: Path | None = None,
    state_dir: Path | None = None,
) -> tuple[dict, int]:
    """Run summon.py via subprocess and return (parsed_json, return_code).

    Global options ``--root`` and ``--state-dir`` are injected before the
    subcommand arguments when the corresponding keyword arguments are given.
    """
    cmd: list[str] = ["uv", "run", str(SUMMON_SCRIPT)]

    if agent_ops_root is not None:
        cmd.extend(["--root", str(agent_ops_root)])
    if state_dir is not None:
        cmd.extend(["--state-dir", str(state_dir)])

    cmd.extend(args)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=60,
    )

    try:
        data = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        data = {"_raw_stdout": result.stdout, "_raw_stderr": result.stderr}

    return data, result.returncode
