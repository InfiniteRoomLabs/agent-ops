# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""SUMMON -- agent discovery, inspection, and session management CLI.

Usage:
  uv run summon.py [--root PATH] [--state-dir PATH] <command> [options]
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated, Optional

import typer
import yaml
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent  # plugins/core
DEFAULT_AGENT_OPS_ROOT = PLUGIN_ROOT.parent.parent  # agent-ops repo root

KNOWN_NAMESPACES = ("core", "engineering", "operations", "research", "finance")

# ---------------------------------------------------------------------------
# Module-level overrides (set by the global callback)
# ---------------------------------------------------------------------------

_root_override: Path | None = None
_state_dir_override: Path | None = None


def get_root() -> Path:
    """Return the effective agent-ops root directory."""
    return _root_override or DEFAULT_AGENT_OPS_ROOT


def get_state_dir() -> Path:
    """Return the effective state directory.

    Default: derive from CWD using Claude Code's project memory path
    pattern -- ``~/.claude/projects/-{slug}/memory/summon/`` where
    *slug* is the CWD with ``/`` replaced by ``-``.
    """
    if _state_dir_override is not None:
        return _state_dir_override

    cwd = Path.cwd().resolve()
    slug = str(cwd).replace("/", "-")
    return Path.home() / ".claude" / "projects" / slug / "memory" / "summon"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AgentSummary(BaseModel):
    name: str = ""
    plugin: str = ""
    description: str = ""
    model: str = ""
    color: str = ""


class AgentDetail(BaseModel):
    name: str = ""
    plugin: str = ""
    path: str = ""
    description: str = ""
    model: str = ""
    tools: str = ""
    color: str = ""
    tags: dict = Field(default_factory=dict)
    body: str = ""


class DiscoverResult(BaseModel):
    found: bool = False
    matches: list[AgentDetail] = Field(default_factory=list)
    agent: AgentDetail | None = None


class ListResult(BaseModel):
    agents: list[AgentSummary] = Field(default_factory=list)


class StateData(BaseModel):
    active_agent: str = ""
    plugin: str = ""
    source_file: str = ""
    loaded_at: str = ""
    session_id: str = ""


class StateCheckResult(BaseModel):
    active: bool = False
    agent: StateData | None = None
    stale: bool = False


class ValidateResult(BaseModel):
    valid: bool = True
    errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def emit(data: BaseModel) -> None:
    """Print a Pydantic model as JSON to stdout."""
    print(data.model_dump_json())


def parse_frontmatter(content: str) -> tuple[dict, str]:
    """Split a markdown file on ``---`` markers and parse the YAML header.

    Returns ``(metadata_dict, body_text)``.
    """
    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)
    match = pattern.match(content)
    if not match:
        return {}, content

    raw_yaml, body = match.group(1), match.group(2)
    try:
        meta = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, body.strip()


def load_registry(root: Path) -> dict:
    """Load ``registry.yaml`` from the agent-ops root."""
    registry_path = root / "registry.yaml"
    if not registry_path.exists():
        return {}
    with open(registry_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def resolve_agent_path(root: Path, registry_entry: dict, name: str) -> Path | None:
    """Resolve a registry entry to the agent's ``.md`` file on disk.

    Tries the registry ``path`` field first (appending ``.md``), then
    falls back to plugin-based conventional path.
    """
    # Try explicit registry path
    reg_path = registry_entry.get("path", "")
    if reg_path:
        candidate = root / f"{reg_path}.md"
        if candidate.exists():
            return candidate

    # Fallback: plugins/<plugin>/agents/<name>.md
    plugin = registry_entry.get("plugin", "")
    if plugin:
        candidate = root / "plugins" / plugin / "agents" / f"{name}.md"
        if candidate.exists():
            return candidate

    return None


def read_agent_file(path: Path) -> AgentDetail | None:
    """Parse an agent ``.md`` file into an ``AgentDetail`` model."""
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)
    if not meta:
        return None

    return AgentDetail(
        name=path.stem,
        plugin=_infer_plugin(path),
        path=str(path),
        description=meta.get("description", ""),
        model=meta.get("model", ""),
        tools=meta.get("tools", ""),
        color=meta.get("color", ""),
        tags=meta.get("tags", {}),
        body=body,
    )


def _infer_plugin(path: Path) -> str:
    """Infer the plugin name from a file path by looking for known namespaces."""
    parts = path.parts
    for ns in KNOWN_NAMESPACES:
        if ns in parts:
            return ns
    return ""


# ---------------------------------------------------------------------------
# CLI definition
# ---------------------------------------------------------------------------

app = typer.Typer(
    help="SUMMON -- agent discovery, inspection, and session management.",
    no_args_is_help=True,
)

state_app = typer.Typer(
    help="Manage agent session state.",
    no_args_is_help=True,
)
app.add_typer(state_app, name="state")


@app.callback()
def main_callback(
    root: Annotated[
        Optional[Path],
        typer.Option("--root", help="Override the agent-ops root directory."),
    ] = None,
    state_dir: Annotated[
        Optional[Path],
        typer.Option("--state-dir", help="Override the state directory."),
    ] = None,
) -> None:
    """Global options applied before any subcommand."""
    global _root_override, _state_dir_override  # noqa: PLW0603
    if root is not None:
        _root_override = root.resolve()
    if state_dir is not None:
        _state_dir_override = state_dir.resolve()


# ---------------------------------------------------------------------------
# Top-level subcommands (stubs returning valid JSON)
# ---------------------------------------------------------------------------


def _list_from_registry(
    root: Path, agents_section: dict, namespace: str | None
) -> list[AgentSummary]:
    """Build agent summaries from the registry.yaml agents section."""
    summaries: list[AgentSummary] = []
    for name, entry in agents_section.items():
        # Apply namespace filter when requested
        if namespace is not None and entry.get("plugin", "") != namespace:
            continue

        agent_path = resolve_agent_path(root, entry, name)
        if agent_path is not None:
            detail = read_agent_file(agent_path)
            if detail is not None:
                summaries.append(
                    AgentSummary(
                        name=detail.name,
                        plugin=detail.plugin,
                        description=detail.description,
                        model=detail.model,
                        color=detail.color,
                    )
                )
            else:
                summaries.append(
                    AgentSummary(name=name, plugin=entry.get("plugin", ""))
                )
        else:
            summaries.append(
                AgentSummary(name=name, plugin=entry.get("plugin", ""))
            )
    return summaries


def _list_from_filesystem(
    root: Path, namespace: str | None
) -> list[AgentSummary]:
    """Scan the filesystem for agent .md files and build summaries."""
    summaries: list[AgentSummary] = []
    namespaces = (namespace,) if namespace else KNOWN_NAMESPACES
    for ns in namespaces:
        agents_dir = root / "plugins" / ns / "agents"
        if not agents_dir.is_dir():
            continue
        for md_file in sorted(agents_dir.glob("*.md")):
            detail = read_agent_file(md_file)
            if detail is not None:
                summaries.append(
                    AgentSummary(
                        name=detail.name,
                        plugin=detail.plugin,
                        description=detail.description,
                        model=detail.model,
                        color=detail.color,
                    )
                )
    return summaries


@app.command()
def list(
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Filter agents by plugin namespace."),
    ] = None,
) -> None:
    """List all registered agents."""
    root = get_root()
    registry = load_registry(root)
    agents_section = registry.get("agents", {})

    if agents_section:
        summaries = _list_from_registry(root, agents_section, namespace)
    else:
        summaries = _list_from_filesystem(root, namespace)

    emit(ListResult(agents=summaries))


@app.command()
def discover(
    query: Annotated[
        Optional[str],
        typer.Argument(help="Search query to match against agents."),
    ] = None,
) -> None:
    """Discover agents matching a query."""
    emit(DiscoverResult())


@app.command()
def info(
    name: Annotated[
        Optional[str],
        typer.Argument(help="Agent name to look up."),
    ] = None,
) -> None:
    """Show detailed info for a specific agent."""
    emit(AgentDetail())


@app.command()
def validate() -> None:
    """Validate registry and agent files."""
    emit(ValidateResult())


# ---------------------------------------------------------------------------
# State subcommands (stubs)
# ---------------------------------------------------------------------------


@state_app.command("create")
def state_create(
    agent: Annotated[
        Optional[str],
        typer.Argument(help="Agent name to activate."),
    ] = None,
) -> None:
    """Create a new agent session."""
    emit(StateData())


@state_app.command("check")
def state_check() -> None:
    """Check current agent session state."""
    emit(StateCheckResult())


@state_app.command("clean")
def state_clean() -> None:
    """Clean up stale session state."""
    emit(StateCheckResult())


@state_app.command("delete")
def state_delete() -> None:
    """Delete the current agent session."""
    emit(StateCheckResult())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
