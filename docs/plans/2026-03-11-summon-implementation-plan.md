# SUMMON Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the SUMMON runtime agent loading system for the agent-ops core plugin -- `/load-agent` and `/end-agent-session` slash commands backed by a Python CLI (`summon.py`) that handles discovery, state management, and validation.

**Architecture:** A Python CLI (`summon.py`) handles all deterministic work (registry search, filesystem discovery, YAML frontmatter parsing, JSON state CRUD, agent validation). Two thin slash commands route to two skills. The skills instruct the LLM to call the CLI, then handle persona injection/teardown. Hooks keep state consistent across session restarts and context compaction.

**Tech Stack:** Python 3.11+ (via `uv run`), Typer (CLI framework), Pydantic (data models), PyYAML (frontmatter/registry parsing), pytest (testing)

**Design doc:** `ideas/docs/plans/2026-03-11-summon-design.md`

---

## File Inventory

All paths relative to `agent-ops/`.

| Action | Path | Purpose |
|--------|------|---------|
| CREATE | `plugins/core/scripts/summon.py` | Python CLI -- the engine |
| CREATE | `plugins/core/hooks/hooks.json` | SessionStart + PreCompact hooks |
| CREATE | `plugins/core/commands/load-agent.md` | Thin command router |
| CREATE | `plugins/core/commands/end-agent-session.md` | Thin command router |
| CREATE | `plugins/core/skills/load-agent/SKILL.md` | Persona injection logic |
| CREATE | `plugins/core/skills/end-agent-session/SKILL.md` | Teardown logic |
| CREATE | `plugins/core/pyproject.toml` | Dev/test dependencies |
| CREATE | `plugins/core/tests/conftest.py` | Shared test fixtures |
| CREATE | `plugins/core/tests/test_summon.py` | All CLI tests |
| MODIFY | `registry.yaml` | 4 new entries (2 skills + 2 commands) |
| MODIFY | `.gitignore` | Add summon state directory pattern |

---

## Key Design Decisions for Implementer

1. **CLI parameter strategy:** The script accepts `--registry`, `--plugins-dir`, and `--state-dir` parameters with defaults computed from `CLAUDE_PLUGIN_ROOT` env var. This makes it testable without the Claude Code environment.

2. **Staleness detection:** `state clean --if-stale` reads `CLAUDE_SESSION_ID` env var and compares to stored `session_id`. Falls back to 24-hour TTL if env var is not set.

3. **PreCompact hook:** Uses a `state reminder` subcommand that outputs the reminder block to stdout if an agent is active, or nothing if not. The hook type is `command` (not `prompt`).

4. **Namespace discovery:** The script discovers valid namespaces by listing `{plugins-dir}/*/` directories rather than hardcoding them.

5. **Name matching:** Substring matching only (MVP). `cto` matches `devops-cto`. Case-insensitive.

6. **Frontmatter parsing:** Split on `---` markers, parse inner YAML with PyYAML, extract markdown body after second `---`.

---

## Task 1: Scaffolding and Test Infrastructure

**Files:**
- Create: `plugins/core/pyproject.toml`
- Create: `plugins/core/tests/conftest.py`
- Create: `plugins/core/tests/test_summon.py` (empty initially)
- Modify: `.gitignore`

**Step 1: Create the pyproject.toml**

```toml
[project]
name = "agent-ops-core"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pydantic>=2",
    "typer>=0.15",
    "pyyaml>=6",
]

[project.optional-dependencies]
test = ["pytest>=8"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 2: Create the test fixtures in conftest.py**

This fixture creates a temporary agent-ops-like directory structure with mock registry and agent files.

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml


@pytest.fixture()
def agent_ops_root(tmp_path: Path) -> Path:
    """Create a mock agent-ops directory structure for testing."""
    root = tmp_path / "agent-ops"
    root.mkdir()

    # -- Plugin directories --
    for ns in ("core", "engineering", "research"):
        agents_dir = root / "plugins" / ns / "agents"
        agents_dir.mkdir(parents=True)

    # -- Mock agent files --
    (root / "plugins" / "engineering" / "agents" / "devops-cto.md").write_text(
        '---\n'
        'description: Strategic technology leadership for DevOps\n'
        'model: opus\n'
        'tools: Glob, Grep, Read\n'
        'color: red\n'
        'tags:\n'
        '  function: [engineering, executive]\n'
        '  scenario: [infrastructure, architecture]\n'
        '---\n'
        '\n'
        '# DevOps CTO\n'
        '\n'
        'You are the CTO of the DevOps division.\n'
        '\n'
        '## Your Role\n'
        '\n'
        'Lead with strategy.\n'
    )

    (root / "plugins" / "engineering" / "agents" / "devops-manager.md").write_text(
        '---\n'
        'description: Pipeline design and deployment coordination\n'
        'model: sonnet\n'
        'tools: Glob, Grep, Read, Write, Edit, Bash\n'
        'color: blue\n'
        'tags:\n'
        '  function: [engineering]\n'
        '  scenario: [deployment, pipeline]\n'
        '---\n'
        '\n'
        '# DevOps Manager\n'
        '\n'
        'You are the DevOps Manager.\n'
    )

    (root / "plugins" / "research" / "agents" / "tech-evaluator.md").write_text(
        '---\n'
        'description: Evaluates and compares technologies\n'
        'model: sonnet\n'
        'tools: WebSearch, WebFetch, Read\n'
        'color: green\n'
        'tags:\n'
        '  function: [research, engineering]\n'
        '  scenario: [technology-evaluation]\n'
        '---\n'
        '\n'
        '# Tech Evaluator\n'
        '\n'
        'You evaluate technologies.\n'
    )

    # -- Mock registry.yaml --
    registry = {
        "agents": {
            "devops-cto": {
                "plugin": "engineering",
                "path": "plugins/engineering/agents/devops-cto",
                "function": ["engineering", "executive"],
                "scenario": ["infrastructure", "architecture"],
                "status": "active",
            },
            "devops-manager": {
                "plugin": "engineering",
                "path": "plugins/engineering/agents/devops-manager",
                "function": ["engineering"],
                "scenario": ["deployment", "pipeline"],
                "status": "active",
            },
            "tech-evaluator": {
                "plugin": "research",
                "path": "plugins/research/agents/tech-evaluator",
                "function": ["research", "engineering"],
                "scenario": ["technology-evaluation"],
                "status": "active",
            },
        },
        "skills": {},
        "commands": {},
    }
    (root / "registry.yaml").write_text(yaml.dump(registry, default_flow_style=False))

    return root


@pytest.fixture()
def state_dir(tmp_path: Path) -> Path:
    """Create a temporary state directory."""
    d = tmp_path / "summon-state"
    d.mkdir()
    return d
```

**Step 3: Create empty test file**

```python
"""Tests for summon.py CLI."""
```

**Step 4: Add summon state pattern to .gitignore**

Append to `.gitignore`:

```
# SUMMON runtime state (never commit)
.summon/
**/summon/state.json
```

**Step 5: Verify test infrastructure works**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops/plugins/core && uv run --extra test pytest tests/ -v`

Expected: 0 tests collected, no errors.

**Step 6: Commit**

```bash
git add plugins/core/pyproject.toml plugins/core/tests/ .gitignore
git commit -m "feat(summon): scaffold test infrastructure for SUMMON CLI"
```

---

## Task 2: summon.py Skeleton with Shared Models

**Files:**
- Create: `plugins/core/scripts/summon.py` (replaces `.gitkeep`)
- Modify: `plugins/core/tests/test_summon.py`

**Step 1: Write a failing test for the CLI app**

Add to `tests/test_summon.py`:

```python
"""Tests for summon.py CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from scripts.summon import app

runner = CliRunner()


def test_app_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "summon" in result.stdout.lower() or "Usage" in result.stdout
```

**Step 2: Run test to verify it fails**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py::test_app_no_args_shows_help -v`

Expected: FAIL (ImportError -- scripts/summon.py doesn't exist yet)

**Step 3: Create the summon.py skeleton**

Delete `plugins/core/scripts/.gitkeep` and create `plugins/core/scripts/summon.py`:

```python
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""SUMMON -- Runtime agent loading CLI for agent-ops.

Handles discovery, validation, and state management for dynamically
loading agent personas in Claude Code sessions.

Usage (standalone):
  uv run summon.py list
  uv run summon.py discover devops-cto
  uv run summon.py state check

Usage (from hooks/skills):
  uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py <subcommand>
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# CLI app
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="summon",
    help="Runtime agent loading CLI for agent-ops.",
    no_args_is_help=True,
)

state_app = typer.Typer(help="Manage SUMMON session state.")
app.add_typer(state_app, name="state")

# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT", "."))
DEFAULT_REPO_ROOT = PLUGIN_ROOT / ".." / ".."
DEFAULT_REGISTRY = DEFAULT_REPO_ROOT / "registry.yaml"
DEFAULT_PLUGINS_DIR = DEFAULT_REPO_ROOT / "plugins"
DEFAULT_STATE_DIR = Path(os.environ.get("SUMMON_STATE_DIR", ".summon"))
STALE_HOURS = 24

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AgentFrontmatter(BaseModel):
    """Parsed YAML frontmatter from an agent definition file."""

    description: str = ""
    model: str = "sonnet"
    tools: str = ""
    color: str = ""
    tags: dict[str, list[str]] = {}


class AgentInfo(BaseModel):
    """Full agent information for discovery results."""

    name: str
    plugin: str
    path: str
    description: str = ""
    model: str = "sonnet"
    color: str = ""
    frontmatter: dict = {}
    body: str = ""
    first_paragraph: str = ""


class StateData(BaseModel):
    """SUMMON session state."""

    active_agent: str
    plugin: str
    source_file: str
    loaded_at: str
    session_id: str


class DiscoverResult(BaseModel):
    """Result of agent discovery."""

    found: bool
    matches: list[AgentInfo] = []
    agent: AgentInfo | None = None


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split a markdown file into YAML frontmatter dict and body text.

    Returns ({}, full_content) if no valid frontmatter found.
    """
    if not content.startswith("---"):
        return {}, content

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}, content

    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return fm, body


def first_paragraph(body: str) -> str:
    """Extract the first non-heading paragraph from markdown body."""
    lines: list[str] = []
    in_paragraph = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if in_paragraph:
                break
            continue
        if not stripped:
            if in_paragraph:
                break
            continue
        in_paragraph = True
        lines.append(stripped)
    return " ".join(lines)


def load_registry(registry_path: Path) -> dict:
    """Load and return registry.yaml contents."""
    if not registry_path.is_file():
        return {"agents": {}, "skills": {}, "commands": {}}
    return yaml.safe_load(registry_path.read_text()) or {}


def discover_namespaces(plugins_dir: Path) -> list[str]:
    """Discover valid namespace names from plugin directory listing."""
    if not plugins_dir.is_dir():
        return []
    return sorted(
        d.name for d in plugins_dir.iterdir() if d.is_dir() and not d.name.startswith(".")
    )


def parse_agent_file(path: Path, plugin: str) -> AgentInfo:
    """Parse an agent .md file into an AgentInfo."""
    content = path.read_text()
    fm, body = parse_frontmatter(content)
    parsed = AgentFrontmatter.model_validate(fm)
    return AgentInfo(
        name=path.stem,
        plugin=plugin,
        path=str(path),
        description=parsed.description,
        model=parsed.model,
        color=parsed.color,
        frontmatter=fm,
        body=body,
        first_paragraph=first_paragraph(body),
    )


def emit(data: BaseModel | dict) -> None:
    """Print structured JSON to stdout."""
    if isinstance(data, BaseModel):
        typer.echo(data.model_dump_json(indent=2))
    else:
        typer.echo(json.dumps(data, indent=2))


# ---------------------------------------------------------------------------
# Subcommands -- stubs (implemented in subsequent tasks)
# ---------------------------------------------------------------------------


@app.command()
def list_agents(
    namespace: Annotated[
        Optional[str], typer.Option("--namespace", "-n", help="Filter by plugin namespace")
    ] = None,
    registry: Annotated[
        Optional[Path], typer.Option("--registry", help="Path to registry.yaml")
    ] = None,
    plugins_dir: Annotated[
        Optional[Path], typer.Option("--plugins-dir", help="Path to plugins directory")
    ] = None,
) -> None:
    """List all available agents grouped by plugin."""
    typer.echo(json.dumps({"agents": []}, indent=2))


@app.command()
def discover(
    name: Annotated[str, typer.Argument(help="Agent name to search for")],
    namespace: Annotated[
        Optional[str], typer.Option("--namespace", "-n", help="Filter by plugin namespace")
    ] = None,
    registry: Annotated[
        Optional[Path], typer.Option("--registry", help="Path to registry.yaml")
    ] = None,
    plugins_dir: Annotated[
        Optional[Path], typer.Option("--plugins-dir", help="Path to plugins directory")
    ] = None,
) -> None:
    """Find an agent definition by name."""
    emit(DiscoverResult(found=False))


@app.command()
def info(
    name: Annotated[str, typer.Argument(help="Agent name")],
    namespace: Annotated[
        Optional[str], typer.Option("--namespace", "-n", help="Filter by plugin namespace")
    ] = None,
    registry: Annotated[
        Optional[Path], typer.Option("--registry", help="Path to registry.yaml")
    ] = None,
    plugins_dir: Annotated[
        Optional[Path], typer.Option("--plugins-dir", help="Path to plugins directory")
    ] = None,
) -> None:
    """Show agent details without loading."""
    emit({"agent": None})


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Path to agent definition file")],
) -> None:
    """Validate an agent definition file."""
    emit({"valid": False, "errors": ["not implemented"]})


# -- State subcommands --


@state_app.command("create")
def state_create(
    agent: Annotated[str, typer.Option("--agent", help="Agent name")],
    plugin: Annotated[str, typer.Option("--plugin", help="Plugin namespace")],
    source: Annotated[Path, typer.Option("--source", help="Path to agent source file")],
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Write session state file."""
    emit({"created": False})


@state_app.command("check")
def state_check(
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Read state and check for active session."""
    emit({"active": False})


@state_app.command("clean")
def state_clean(
    if_stale: Annotated[
        bool, typer.Option("--if-stale", help="Only clean if state is stale")
    ] = False,
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Delete stale or orphaned state."""
    emit({"cleaned": False})


@state_app.command("delete")
def state_delete(
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Clean teardown -- delete state file."""
    emit({"deleted": False})


@state_app.command("reminder")
def state_reminder(
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Output compact persona reminder for PreCompact hook. Prints nothing if no active session."""
    pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
```

**Step 4: Run test to verify it passes**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py::test_app_no_args_shows_help -v`

Expected: PASS

**Step 5: Commit**

```bash
git add plugins/core/scripts/summon.py plugins/core/tests/test_summon.py
git rm plugins/core/scripts/.gitkeep
git commit -m "feat(summon): add CLI skeleton with models and stub subcommands"
```

---

## Task 3: `list` Subcommand

**Files:**
- Modify: `plugins/core/scripts/summon.py` (the `list_agents` function)
- Modify: `plugins/core/tests/test_summon.py`

**Step 1: Write failing tests for `list`**

Add to `tests/test_summon.py`:

```python
import json
from pathlib import Path


def test_list_all_agents(agent_ops_root: Path):
    """List returns all agents from registry."""
    result = runner.invoke(app, [
        "list-agents",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    names = [a["name"] for a in data["agents"]]
    assert "devops-cto" in names
    assert "devops-manager" in names
    assert "tech-evaluator" in names


def test_list_filtered_by_namespace(agent_ops_root: Path):
    """List with --namespace filters to that plugin only."""
    result = runner.invoke(app, [
        "list-agents",
        "--namespace", "engineering",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    names = [a["name"] for a in data["agents"]]
    assert "devops-cto" in names
    assert "tech-evaluator" not in names


def test_list_empty_namespace(agent_ops_root: Path):
    """List with unknown namespace returns empty list."""
    result = runner.invoke(app, [
        "list-agents",
        "--namespace", "nonexistent",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["agents"] == []
```

**Step 2: Run tests to verify they fail**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py -k "test_list" -v`

Expected: FAIL (list returns empty `{"agents": []}` for all cases)

**Step 3: Implement the `list_agents` function**

Replace the `list_agents` stub in `summon.py`:

```python
@app.command()
def list_agents(
    namespace: Annotated[
        Optional[str], typer.Option("--namespace", "-n", help="Filter by plugin namespace")
    ] = None,
    registry: Annotated[
        Optional[Path], typer.Option("--registry", help="Path to registry.yaml")
    ] = None,
    plugins_dir: Annotated[
        Optional[Path], typer.Option("--plugins-dir", help="Path to plugins directory")
    ] = None,
) -> None:
    """List all available agents grouped by plugin."""
    reg_path = registry or DEFAULT_REGISTRY
    plug_dir = plugins_dir or DEFAULT_PLUGINS_DIR
    reg = load_registry(reg_path)

    agents: list[dict] = []
    for agent_name, entry in reg.get("agents", {}).items():
        if namespace and entry.get("plugin") != namespace:
            continue

        # Try to parse the actual agent file for richer info
        agent_file = plug_dir / entry["plugin"] / "agents" / f"{agent_name}.md"
        if agent_file.is_file():
            info = parse_agent_file(agent_file, entry["plugin"])
            agents.append({
                "name": info.name,
                "plugin": info.plugin,
                "description": info.description,
                "model": info.model,
                "color": info.color,
            })
        else:
            agents.append({
                "name": agent_name,
                "plugin": entry.get("plugin", "unknown"),
                "description": "",
                "model": "sonnet",
                "color": "",
            })

    emit({"agents": agents})
```

**Step 4: Run tests to verify they pass**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py -k "test_list" -v`

Expected: PASS (all 3 tests)

**Step 5: Commit**

```bash
git add plugins/core/scripts/summon.py plugins/core/tests/test_summon.py
git commit -m "feat(summon): implement list subcommand with namespace filtering"
```

---

## Task 4: `discover` Subcommand

**Files:**
- Modify: `plugins/core/scripts/summon.py` (the `discover` function + helper)
- Modify: `plugins/core/tests/test_summon.py`

This is the core discovery algorithm from design doc section 6.

**Step 1: Write failing tests for discovery**

Add to `tests/test_summon.py`:

```python
def test_discover_exact_match(agent_ops_root: Path):
    """Discover finds exact match in registry."""
    result = runner.invoke(app, [
        "discover", "devops-cto",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["found"] is True
    assert data["agent"]["name"] == "devops-cto"
    assert data["agent"]["plugin"] == "engineering"
    assert len(data["agent"]["body"]) > 0


def test_discover_substring_match(agent_ops_root: Path):
    """Discover finds agents via substring matching."""
    result = runner.invoke(app, [
        "discover", "cto",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["found"] is True
    assert data["agent"]["name"] == "devops-cto"


def test_discover_with_namespace(agent_ops_root: Path):
    """Discover filters by namespace."""
    result = runner.invoke(app, [
        "discover", "devops-cto",
        "--namespace", "engineering",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["found"] is True
    assert data["agent"]["plugin"] == "engineering"


def test_discover_multiple_matches(agent_ops_root: Path):
    """Discover returns multiple matches for disambiguation."""
    result = runner.invoke(app, [
        "discover", "devops",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["found"] is False
    assert len(data["matches"]) >= 2


def test_discover_not_found(agent_ops_root: Path):
    """Discover returns not found for nonexistent agent."""
    result = runner.invoke(app, [
        "discover", "nonexistent-agent",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["found"] is False
    assert len(data["matches"]) == 0


def test_discover_filesystem_fallback(agent_ops_root: Path):
    """Discover finds agents via filesystem when not in registry."""
    # Add an agent file that's NOT in registry
    extra = agent_ops_root / "plugins" / "core" / "agents" / "secret-agent.md"
    extra.write_text(
        '---\n'
        'description: A secret agent not in registry\n'
        '---\n'
        '\n'
        '# Secret Agent\n'
        '\n'
        'You are secret.\n'
    )

    result = runner.invoke(app, [
        "discover", "secret-agent",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["found"] is True
    assert data["agent"]["name"] == "secret-agent"


def test_discover_case_insensitive(agent_ops_root: Path):
    """Discover is case-insensitive."""
    result = runner.invoke(app, [
        "discover", "DEVOPS-CTO",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["found"] is True
    assert data["agent"]["name"] == "devops-cto"
```

**Step 2: Run tests to verify they fail**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py -k "test_discover" -v`

Expected: FAIL (discover returns `found: false` for all cases)

**Step 3: Add the discovery helper function**

Add to `summon.py` in the utility functions section:

```python
def _discover_agents(
    name: str,
    namespace: str | None,
    registry_path: Path,
    plugins_dir: Path,
) -> DiscoverResult:
    """Core discovery algorithm.

    Resolution order:
    1. Registry fast-path (exact then substring)
    2. Filesystem glob fallback
    3. Disambiguation if multiple matches
    """
    query = name.lower()

    # -- Phase 1: Registry search --
    reg = load_registry(registry_path)
    registry_agents = reg.get("agents", {})

    candidates: list[AgentInfo] = []

    for agent_name, entry in registry_agents.items():
        if namespace and entry.get("plugin") != namespace:
            continue

        if query == agent_name.lower():
            # Exact match -- try to load full file
            agent_file = plugins_dir / entry["plugin"] / "agents" / f"{agent_name}.md"
            if agent_file.is_file():
                agent = parse_agent_file(agent_file, entry["plugin"])
            else:
                agent = AgentInfo(
                    name=agent_name,
                    plugin=entry.get("plugin", "unknown"),
                    path=entry.get("path", ""),
                    description="",
                )
            return DiscoverResult(found=True, matches=[agent], agent=agent)

    # Substring match in registry
    for agent_name, entry in registry_agents.items():
        if namespace and entry.get("plugin") != namespace:
            continue
        if query in agent_name.lower():
            agent_file = plugins_dir / entry["plugin"] / "agents" / f"{agent_name}.md"
            if agent_file.is_file():
                candidates.append(parse_agent_file(agent_file, entry["plugin"]))
            else:
                candidates.append(AgentInfo(
                    name=agent_name,
                    plugin=entry.get("plugin", "unknown"),
                    path=entry.get("path", ""),
                ))

    if len(candidates) == 1:
        return DiscoverResult(found=True, matches=candidates, agent=candidates[0])
    if len(candidates) > 1:
        return DiscoverResult(found=False, matches=candidates)

    # -- Phase 2: Filesystem fallback --
    glob_pattern = "agents/*.md"
    search_dirs: list[Path] = []
    if namespace:
        ns_dir = plugins_dir / namespace
        if ns_dir.is_dir():
            search_dirs.append(ns_dir)
    else:
        search_dirs = [
            d for d in plugins_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

    fs_candidates: list[AgentInfo] = []
    for plugin_dir in search_dirs:
        for agent_file in sorted((plugin_dir / "agents").glob("*.md")):
            file_name = agent_file.stem.lower()
            if query == file_name or query in file_name:
                fs_candidates.append(parse_agent_file(agent_file, plugin_dir.name))

    if len(fs_candidates) == 1:
        return DiscoverResult(found=True, matches=fs_candidates, agent=fs_candidates[0])
    if len(fs_candidates) > 1:
        return DiscoverResult(found=False, matches=fs_candidates)

    return DiscoverResult(found=False, matches=[])
```

**Step 4: Update the `discover` command to use the helper**

Replace the `discover` stub:

```python
@app.command()
def discover(
    name: Annotated[str, typer.Argument(help="Agent name to search for")],
    namespace: Annotated[
        Optional[str], typer.Option("--namespace", "-n", help="Filter by plugin namespace")
    ] = None,
    registry: Annotated[
        Optional[Path], typer.Option("--registry", help="Path to registry.yaml")
    ] = None,
    plugins_dir: Annotated[
        Optional[Path], typer.Option("--plugins-dir", help="Path to plugins directory")
    ] = None,
) -> None:
    """Find an agent definition by name."""
    reg_path = registry or DEFAULT_REGISTRY
    plug_dir = plugins_dir or DEFAULT_PLUGINS_DIR
    result = _discover_agents(name, namespace, reg_path, plug_dir)
    emit(result)
```

**Step 5: Run tests to verify they pass**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py -k "test_discover" -v`

Expected: PASS (all 7 tests)

**Step 6: Commit**

```bash
git add plugins/core/scripts/summon.py plugins/core/tests/test_summon.py
git commit -m "feat(summon): implement discover subcommand with registry + filesystem fallback"
```

---

## Task 5: `info` and `validate` Subcommands

**Files:**
- Modify: `plugins/core/scripts/summon.py`
- Modify: `plugins/core/tests/test_summon.py`

**Step 1: Write failing tests**

Add to `tests/test_summon.py`:

```python
def test_info_shows_agent_details(agent_ops_root: Path):
    """Info returns agent details with first paragraph."""
    result = runner.invoke(app, [
        "info", "devops-cto",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["agent"] is not None
    assert data["agent"]["name"] == "devops-cto"
    assert data["agent"]["first_paragraph"] != ""
    assert "body" not in data["agent"]  # info should NOT include full body


def test_info_not_found(agent_ops_root: Path):
    """Info returns null agent when not found."""
    result = runner.invoke(app, [
        "info", "nonexistent",
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["agent"] is None


def test_validate_valid_agent(agent_ops_root: Path):
    """Validate passes for a well-formed agent file."""
    path = agent_ops_root / "plugins" / "engineering" / "agents" / "devops-cto.md"
    result = runner.invoke(app, ["validate", str(path)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["valid"] is True
    assert data["errors"] == []


def test_validate_missing_frontmatter(tmp_path: Path):
    """Validate fails for agent file without frontmatter."""
    bad_file = tmp_path / "bad-agent.md"
    bad_file.write_text("# No Frontmatter\n\nJust some text.\n")
    result = runner.invoke(app, ["validate", str(bad_file)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["valid"] is False
    assert len(data["errors"]) > 0


def test_validate_missing_description(tmp_path: Path):
    """Validate fails for agent file without description."""
    bad_file = tmp_path / "no-desc.md"
    bad_file.write_text("---\nmodel: sonnet\n---\n\n# Agent\n\nBody text.\n")
    result = runner.invoke(app, ["validate", str(bad_file)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["valid"] is False
    assert any("description" in e.lower() for e in data["errors"])


def test_validate_nonexistent_file():
    """Validate fails for nonexistent file."""
    result = runner.invoke(app, ["validate", "/nonexistent/path.md"])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["valid"] is False
```

**Step 2: Run tests to verify they fail**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py -k "test_info or test_validate" -v`

Expected: FAIL

**Step 3: Implement `info` command**

Replace the `info` stub:

```python
@app.command()
def info(
    name: Annotated[str, typer.Argument(help="Agent name")],
    namespace: Annotated[
        Optional[str], typer.Option("--namespace", "-n", help="Filter by plugin namespace")
    ] = None,
    registry: Annotated[
        Optional[Path], typer.Option("--registry", help="Path to registry.yaml")
    ] = None,
    plugins_dir: Annotated[
        Optional[Path], typer.Option("--plugins-dir", help="Path to plugins directory")
    ] = None,
) -> None:
    """Show agent details without loading."""
    reg_path = registry or DEFAULT_REGISTRY
    plug_dir = plugins_dir or DEFAULT_PLUGINS_DIR
    result = _discover_agents(name, namespace, reg_path, plug_dir)

    if not result.found or result.agent is None:
        emit({"agent": None})
        return

    # Return info without full body
    agent = result.agent
    emit({
        "agent": {
            "name": agent.name,
            "plugin": agent.plugin,
            "path": agent.path,
            "description": agent.description,
            "model": agent.model,
            "color": agent.color,
            "first_paragraph": agent.first_paragraph,
            "frontmatter": agent.frontmatter,
        }
    })
```

**Step 4: Implement `validate` command**

Replace the `validate` stub:

```python
@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Path to agent definition file")],
) -> None:
    """Validate an agent definition file."""
    errors: list[str] = []

    if not path.is_file():
        emit({"valid": False, "errors": [f"File not found: {path}"]})
        return

    content = path.read_text()

    # Check frontmatter exists
    if not content.startswith("---"):
        errors.append("Missing YAML frontmatter (file must start with ---)")
        emit({"valid": False, "errors": errors})
        return

    fm, body = parse_frontmatter(content)

    if not fm:
        errors.append("Empty or unparseable YAML frontmatter")

    if not fm.get("description"):
        errors.append("Missing required field: description")

    if not body.strip():
        errors.append("Agent body (markdown after frontmatter) is empty")

    emit({"valid": len(errors) == 0, "errors": errors})
```

**Step 5: Run tests to verify they pass**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py -k "test_info or test_validate" -v`

Expected: PASS (all 6 tests)

**Step 6: Commit**

```bash
git add plugins/core/scripts/summon.py plugins/core/tests/test_summon.py
git commit -m "feat(summon): implement info and validate subcommands"
```

---

## Task 6: State Management Subcommands

**Files:**
- Modify: `plugins/core/scripts/summon.py`
- Modify: `plugins/core/tests/test_summon.py`

**Step 1: Write failing tests for state management**

Add to `tests/test_summon.py`:

```python
def test_state_create(state_dir: Path):
    """State create writes state.json."""
    result = runner.invoke(app, [
        "state", "create",
        "--agent", "devops-cto",
        "--plugin", "engineering",
        "--source", "/fake/path/devops-cto.md",
        "--state-dir", str(state_dir),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["created"] is True

    state_file = state_dir / "state.json"
    assert state_file.exists()
    state = json.loads(state_file.read_text())
    assert state["active_agent"] == "devops-cto"
    assert state["plugin"] == "engineering"
    assert "session_id" in state
    assert "loaded_at" in state


def test_state_check_active(state_dir: Path):
    """State check returns active when state exists."""
    # Create state first
    runner.invoke(app, [
        "state", "create",
        "--agent", "devops-cto",
        "--plugin", "engineering",
        "--source", "/fake/path.md",
        "--state-dir", str(state_dir),
    ])
    result = runner.invoke(app, ["state", "check", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["active"] is True
    assert data["agent"]["active_agent"] == "devops-cto"


def test_state_check_inactive(state_dir: Path):
    """State check returns inactive when no state file."""
    result = runner.invoke(app, ["state", "check", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["active"] is False


def test_state_delete(state_dir: Path):
    """State delete removes state.json."""
    runner.invoke(app, [
        "state", "create",
        "--agent", "devops-cto",
        "--plugin", "engineering",
        "--source", "/fake/path.md",
        "--state-dir", str(state_dir),
    ])
    result = runner.invoke(app, ["state", "delete", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["deleted"] is True
    assert not (state_dir / "state.json").exists()


def test_state_delete_noop(state_dir: Path):
    """State delete succeeds even if no state file."""
    result = runner.invoke(app, ["state", "delete", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["deleted"] is False


def test_state_clean_removes_stale(state_dir: Path, monkeypatch):
    """State clean --if-stale removes state with mismatched session_id."""
    # Create state with one session ID
    runner.invoke(app, [
        "state", "create",
        "--agent", "devops-cto",
        "--plugin", "engineering",
        "--source", "/fake/path.md",
        "--state-dir", str(state_dir),
    ])

    # Set a DIFFERENT session ID in the environment
    monkeypatch.setenv("CLAUDE_SESSION_ID", "a-completely-different-session")

    result = runner.invoke(app, [
        "state", "clean", "--if-stale", "--state-dir", str(state_dir),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["cleaned"] is True
    assert not (state_dir / "state.json").exists()


def test_state_clean_keeps_fresh(state_dir: Path, monkeypatch):
    """State clean --if-stale keeps state with matching session_id."""
    runner.invoke(app, [
        "state", "create",
        "--agent", "devops-cto",
        "--plugin", "engineering",
        "--source", "/fake/path.md",
        "--state-dir", str(state_dir),
    ])

    # Read the session_id that was written
    state = json.loads((state_dir / "state.json").read_text())
    monkeypatch.setenv("CLAUDE_SESSION_ID", state["session_id"])

    result = runner.invoke(app, [
        "state", "clean", "--if-stale", "--state-dir", str(state_dir),
    ])
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert data["cleaned"] is False
    assert (state_dir / "state.json").exists()


def test_state_reminder_active(state_dir: Path):
    """State reminder outputs reminder text when agent active."""
    runner.invoke(app, [
        "state", "create",
        "--agent", "devops-cto",
        "--plugin", "engineering",
        "--source", "/fake/path.md",
        "--state-dir", str(state_dir),
    ])
    result = runner.invoke(app, ["state", "reminder", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    assert "AGENT SESSION REMINDER" in result.stdout
    assert "devops-cto" in result.stdout


def test_state_reminder_inactive(state_dir: Path):
    """State reminder outputs nothing when no agent active."""
    result = runner.invoke(app, ["state", "reminder", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    assert result.stdout.strip() == ""
```

**Step 2: Run tests to verify they fail**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py -k "test_state" -v`

Expected: FAIL

**Step 3: Implement state subcommands**

Replace all state stubs in `summon.py`:

```python
def _resolve_state_dir(state_dir: Path | None) -> Path:
    """Resolve the state directory path."""
    return state_dir or DEFAULT_STATE_DIR


def _state_file(state_dir: Path | None) -> Path:
    """Return path to state.json."""
    return _resolve_state_dir(state_dir) / "state.json"


def _read_state(state_dir: Path | None) -> StateData | None:
    """Read state file, return None if not found or invalid."""
    sf = _state_file(state_dir)
    if not sf.is_file():
        return None
    try:
        return StateData.model_validate_json(sf.read_text())
    except Exception:
        return None


def _is_stale(state: StateData) -> bool:
    """Check if state is stale (session mismatch or expired)."""
    current_session = os.environ.get("CLAUDE_SESSION_ID")
    if current_session:
        return state.session_id != current_session

    # Fallback: time-based staleness
    try:
        loaded = datetime.fromisoformat(state.loaded_at)
        age = datetime.now(timezone.utc) - loaded
        return age.total_seconds() > STALE_HOURS * 3600
    except Exception:
        return True


@state_app.command("create")
def state_create(
    agent: Annotated[str, typer.Option("--agent", help="Agent name")],
    plugin: Annotated[str, typer.Option("--plugin", help="Plugin namespace")],
    source: Annotated[Path, typer.Option("--source", help="Path to agent source file")],
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Write session state file."""
    sd = _resolve_state_dir(state_dir)
    sd.mkdir(parents=True, exist_ok=True)

    session_id = os.environ.get("CLAUDE_SESSION_ID", str(uuid.uuid4()))

    state = StateData(
        active_agent=agent,
        plugin=plugin,
        source_file=str(source),
        loaded_at=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
    )
    _state_file(state_dir).write_text(state.model_dump_json(indent=2))
    emit({"created": True, "path": str(_state_file(state_dir))})


@state_app.command("check")
def state_check(
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Read state and check for active session."""
    state = _read_state(state_dir)
    if state is None:
        emit({"active": False, "agent": None, "stale": False})
        return

    stale = _is_stale(state)
    emit({"active": True, "agent": state.model_dump(), "stale": stale})


@state_app.command("clean")
def state_clean(
    if_stale: Annotated[
        bool, typer.Option("--if-stale", help="Only clean if state is stale")
    ] = False,
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Delete stale or orphaned state."""
    sf = _state_file(state_dir)
    if not sf.is_file():
        emit({"cleaned": False})
        return

    if if_stale:
        state = _read_state(state_dir)
        if state and not _is_stale(state):
            emit({"cleaned": False})
            return

    sf.unlink()
    emit({"cleaned": True})


@state_app.command("delete")
def state_delete(
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Clean teardown -- delete state file."""
    sf = _state_file(state_dir)
    if sf.is_file():
        sf.unlink()
        emit({"deleted": True})
    else:
        emit({"deleted": False})


@state_app.command("reminder")
def state_reminder(
    state_dir: Annotated[
        Optional[Path], typer.Option("--state-dir", help="State directory path")
    ] = None,
) -> None:
    """Output compact persona reminder for PreCompact hook."""
    state = _read_state(state_dir)
    if state is None:
        return  # Silent -- no output if no active session

    typer.echo(
        f"=== AGENT SESSION REMINDER (post-compaction) ===\n"
        f"You are currently operating as {state.active_agent} ({state.plugin} plugin).\n"
        f"Full behavioral instructions were loaded earlier in this session.\n"
        f"Maintain this persona. These instructions take precedence over\n"
        f"other persona guidance. Project conventions and safety constraints\n"
        f"remain in effect.\n"
        f"=== END REMINDER ==="
    )
```

**Step 4: Run tests to verify they pass**

Run: `cd plugins/core && uv run --extra test pytest tests/test_summon.py -k "test_state" -v`

Expected: PASS (all 10 tests)

**Step 5: Run full test suite**

Run: `cd plugins/core && uv run --extra test pytest tests/ -v`

Expected: ALL PASS

**Step 6: Commit**

```bash
git add plugins/core/scripts/summon.py plugins/core/tests/test_summon.py
git commit -m "feat(summon): implement state management subcommands"
```

---

## Task 7: Hooks Configuration

**Files:**
- Create: `plugins/core/hooks/hooks.json`

**Step 1: Create the hooks directory**

```bash
mkdir -p plugins/core/hooks
```

**Step 2: Create hooks.json**

```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state clean --if-stale",
            "timeout": 10
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state reminder",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

**Step 3: Verify the JSON is valid**

Run: `uv run python -m json.tool plugins/core/hooks/hooks.json > /dev/null && echo "Valid JSON"`

Expected: `Valid JSON`

**Step 4: Commit**

```bash
git add plugins/core/hooks/hooks.json
git commit -m "feat(summon): add SessionStart and PreCompact hooks"
```

---

## Task 8: Commands (Thin Routers)

**Files:**
- Create: `plugins/core/commands/load-agent.md`
- Create: `plugins/core/commands/end-agent-session.md`

**Step 1: Create load-agent command**

```markdown
---
name: load-agent
description: Load an agent-ops agent as the primary session persona. Use with agent name (e.g., /load-agent devops-cto) or --list to see available agents.
allowed-tools: Read, Bash, Glob, Grep
tags:
  function: [engineering, operations, finance, research]
  scenario: [agent-loading, persona]
  custom: [summon, load, persona]
---

# Load Agent

Load an agent-ops agent as the session persona using the SUMMON system.

**Skill:** This command delegates to the `load-agent` skill. Invoke it now.

**Arguments received:**
```text
$ARGUMENTS
```
```

**Step 2: Create end-agent-session command**

```markdown
---
name: end-agent-session
description: End the current agent session and return to the default orchestrator persona.
allowed-tools: Read, Bash
tags:
  function: [engineering, operations, finance, research]
  scenario: [agent-loading, persona]
  custom: [summon, unload, persona]
---

# End Agent Session

Tear down the currently loaded agent persona using the SUMMON system.

**Skill:** This command delegates to the `end-agent-session` skill. Invoke it now.

**Arguments received:**
```text
$ARGUMENTS
```
```

**Step 3: Commit**

```bash
git add plugins/core/commands/load-agent.md plugins/core/commands/end-agent-session.md
git commit -m "feat(summon): add load-agent and end-agent-session commands"
```

---

## Task 9: Skills (Persona Injection and Teardown Logic)

**Files:**
- Create: `plugins/core/skills/load-agent/SKILL.md`
- Create: `plugins/core/skills/end-agent-session/SKILL.md`

**Step 1: Create the skill directories**

```bash
mkdir -p plugins/core/skills/load-agent
mkdir -p plugins/core/skills/end-agent-session
```

**Step 2: Create load-agent SKILL.md**

This is the most important file -- it tells the LLM how to orchestrate agent loading.

```markdown
---
name: load-agent
description: Load an agent-ops agent as the primary session persona. Use with agent name (e.g., /load-agent devops-cto) or --list to see available agents.
allowed-tools: Read, Bash, Glob, Grep
tags:
  function: [engineering, operations, finance, research]
  scenario: [agent-loading, persona]
  custom: [summon, load, persona]
---

# Load Agent

Load an agent-ops agent as the session persona using the SUMMON runtime loading system.

## Input

```text
$ARGUMENTS
```

## Process

### Step 1: Parse arguments

Parse the user's input to determine intent:

- **No arguments or `--list`**: List all available agents (go to List Flow)
- **`--info <name>`**: Show agent details without loading (go to Info Flow)
- **`<name>`**: Load the agent (go to Load Flow)
- **`<namespace> <name>`**: Load with namespace filter (go to Load Flow)

Determine if the first token is a namespace by checking if it matches a plugin name (core, engineering, operations, research, finance). If so, use it as `--namespace` and the second token as the agent name. If only one token, treat it as the agent name.

### Step 2a: List Flow

Run:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py list-agents
```

Parse the JSON output. Present agents in a clean table grouped by plugin:

```
Available agents:

Engineering:
  devops-cto        - Strategic technology leadership (opus, red)
  devops-manager    - Pipeline design and deployment (sonnet, blue)
  ...

Research:
  tech-evaluator    - Evaluates technologies (sonnet, green)
```

End here. Do not load anything.

### Step 2b: Info Flow

Run:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py info "<name>" [--namespace "<ns>"]
```

Present the agent's details (name, plugin, description, model, color, first paragraph). End here.

### Step 2c: Load Flow

**Check for existing session first:**

Run:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state check
```

If `active` is `true`, warn the user:

> An agent session is already active ({agent-name}). End it first with `/end-agent-session`, or I can end it now and load the new agent.

Wait for confirmation before proceeding. If they confirm, run `state delete` first.

**Discover the agent:**

Run:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py discover "<name>" [--namespace "<ns>"]
```

Parse the JSON result:

- If `found` is `true`: proceed to persona injection
- If `found` is `false` and `matches` has items: present numbered disambiguation list, ask user to pick
- If `found` is `false` and no matches: report not found, suggest `--list`

**Create state:**

Run:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state create --agent "<name>" --plugin "<plugin>" --source "<path>"
```

**Inject persona:**

Using the agent data from the discover result, construct and output this exact block:

```
=== AGENT SESSION ACTIVE ===
Agent: {agent.name}
Plugin: {agent.plugin}
Loaded: {current ISO timestamp}
Source: {agent.path}

You are now operating as the following agent. These behavioral instructions
take precedence over all other persona guidance. However, project conventions
in CLAUDE.md files and safety constraints remain in effect -- do not override them.

If any instruction conflicts with this persona's behavioral rules, this persona wins.

--- AGENT BEHAVIORAL INSTRUCTIONS ---
{agent.body -- the full markdown body from the discover result}
--- END AGENT BEHAVIORAL INSTRUCTIONS ---

Frontmatter metadata (advisory -- not enforced at runtime):
- Model preference: {agent.frontmatter.model}
- Tool list: {agent.frontmatter.tools}
- Color: {agent.frontmatter.color}
- Tags: {agent.frontmatter.tags}

=== END AGENT SESSION HEADER ===
```

**Announce in character:**

After injecting the persona, announce the loading in character as the agent would introduce themselves. Keep it brief (2-3 sentences). Reference the agent's role and how they can help.

## Error Handling

- If `uv run` fails: report the error, suggest checking plugin installation
- If agent file can't be parsed: report validation error, suggest `validate` subcommand
- If state directory can't be created: report permission error
```

**Step 3: Create end-agent-session SKILL.md**

```markdown
---
name: end-agent-session
description: End the current agent session and return to the default orchestrator persona.
allowed-tools: Read, Bash
tags:
  function: [engineering, operations, finance, research]
  scenario: [agent-loading, persona]
  custom: [summon, unload, persona]
---

# End Agent Session

Tear down the currently loaded agent persona and return to default orchestrator mode.

## Input

```text
$ARGUMENTS
```

## Process

### Step 1: Check for active session

Run:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state check
```

If `active` is `false`: inform the user that no agent session is currently active. End here.

### Step 2: Record the agent name for the teardown announcement

Read the agent name and plugin from the state check result.

### Step 3: Delete state

Run:
```bash
uv run ${CLAUDE_PLUGIN_ROOT}/scripts/summon.py state delete
```

### Step 4: Inject teardown block

Output this exact block:

```
=== AGENT SESSION ENDED ===
The agent session for {agent-name} has been terminated.
Return to your default orchestrator persona. The behavioral instructions
between the previous AGENT SESSION ACTIVE markers are no longer in effect.
=== END SESSION TERMINATION ===
```

### Step 5: Confirm to user

Briefly confirm the session has ended in a neutral tone (not in character):

> Agent session ended. {agent-name} ({plugin}) has been unloaded. I'm back to default orchestrator mode.
```

**Step 4: Commit**

```bash
git add plugins/core/skills/load-agent/ plugins/core/skills/end-agent-session/
git commit -m "feat(summon): add load-agent and end-agent-session skills"
```

---

## Task 10: Registry and Config Updates

**Files:**
- Modify: `registry.yaml`
- Delete: `plugins/core/scripts/.gitkeep` (if not already removed)
- Delete: `plugins/core/agents/.gitkeep` (keep the directory from hooks)

**Step 1: Add 4 new entries to registry.yaml**

Add under the `skills:` section:

```yaml
  load-agent:
    plugin: core
    path: plugins/core/skills/load-agent
    function: [engineering, operations, finance, research]
    scenario: [agent-loading, persona]
    status: active

  end-agent-session:
    plugin: core
    path: plugins/core/skills/end-agent-session
    function: [engineering, operations, finance, research]
    scenario: [agent-loading, persona]
    status: active
```

Add under the `commands:` section:

```yaml
  load-agent:
    plugin: core
    path: plugins/core/commands/load-agent
    function: [engineering, operations, finance, research]
    scenario: [agent-loading, persona]
    status: active

  end-agent-session:
    plugin: core
    path: plugins/core/commands/end-agent-session
    function: [engineering, operations, finance, research]
    scenario: [agent-loading, persona]
    status: active
```

**Step 2: Clean up .gitkeep files that are no longer needed**

```bash
# Only remove if the directory now has real content
git rm plugins/core/scripts/.gitkeep 2>/dev/null || true
```

Keep `plugins/core/agents/.gitkeep` since agents/ is still empty for now.

**Step 3: Run the full test suite one final time**

Run: `cd plugins/core && uv run --extra test pytest tests/ -v`

Expected: ALL PASS

**Step 4: Commit**

```bash
git add registry.yaml
git commit -m "feat(summon): register load-agent and end-agent-session in registry"
```

---

## Task 11: Integration Smoke Test

**Files:**
- Modify: `plugins/core/tests/test_summon.py`

**Step 1: Add end-to-end integration test**

Add to `tests/test_summon.py`:

```python
def test_full_lifecycle(agent_ops_root: Path, state_dir: Path):
    """Integration test: list -> discover -> load state -> check -> reminder -> delete."""
    common = [
        "--registry", str(agent_ops_root / "registry.yaml"),
        "--plugins-dir", str(agent_ops_root / "plugins"),
    ]

    # List agents
    result = runner.invoke(app, ["list-agents", *common])
    assert result.exit_code == 0
    agents = json.loads(result.stdout)["agents"]
    assert len(agents) >= 3

    # Discover a specific agent
    result = runner.invoke(app, ["discover", "devops-cto", *common])
    assert result.exit_code == 0
    discover_data = json.loads(result.stdout)
    assert discover_data["found"] is True
    agent = discover_data["agent"]

    # Create state
    result = runner.invoke(app, [
        "state", "create",
        "--agent", agent["name"],
        "--plugin", agent["plugin"],
        "--source", agent["path"],
        "--state-dir", str(state_dir),
    ])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["created"] is True

    # Check state
    result = runner.invoke(app, ["state", "check", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    check = json.loads(result.stdout)
    assert check["active"] is True
    assert check["agent"]["active_agent"] == "devops-cto"

    # Get reminder
    result = runner.invoke(app, ["state", "reminder", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    assert "devops-cto" in result.stdout

    # Delete state (teardown)
    result = runner.invoke(app, ["state", "delete", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["deleted"] is True

    # Confirm state is gone
    result = runner.invoke(app, ["state", "check", "--state-dir", str(state_dir)])
    assert result.exit_code == 0
    assert json.loads(result.stdout)["active"] is False
```

**Step 2: Run the full test suite**

Run: `cd plugins/core && uv run --extra test pytest tests/ -v`

Expected: ALL PASS

**Step 3: Commit**

```bash
git add plugins/core/tests/test_summon.py
git commit -m "test(summon): add end-to-end lifecycle integration test"
```

---

## Post-Implementation Checklist

After all tasks are complete, verify:

- [ ] `uv run plugins/core/scripts/summon.py --help` shows all subcommands
- [ ] `uv run plugins/core/scripts/summon.py list-agents --registry registry.yaml --plugins-dir plugins/` lists all 13 agents
- [ ] `uv run plugins/core/scripts/summon.py discover devops-cto --registry registry.yaml --plugins-dir plugins/` finds the CTO
- [ ] `uv run plugins/core/scripts/summon.py validate plugins/engineering/agents/devops-cto.md` passes
- [ ] Full test suite passes: `cd plugins/core && uv run --extra test pytest tests/ -v`
- [ ] No smart quotes or non-ASCII in any created files
- [ ] All new files are UTF-8

## Dependency Note

The design doc lists "Core Platform Lead agent (idea 032)" as a blocking dependency. This plan implements the infrastructure without that agent. The actual agent file can be created later via the `new-agent` skill when idea 032 is staffed.
