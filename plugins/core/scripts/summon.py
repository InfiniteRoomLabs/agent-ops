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
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
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

_FALLBACK_NAMESPACES = ("core", "engineering", "operations", "research", "finance")


def _discover_namespaces(root: Path) -> tuple[str, ...]:
    """Dynamically discover plugin namespaces from ``plugins/*/`` directories.

    Falls back to a hardcoded tuple if the plugins directory doesn't exist.
    """
    plugins_dir = root / "plugins"
    if plugins_dir.is_dir():
        found = tuple(
            sorted(d.name for d in plugins_dir.iterdir() if d.is_dir())
        )
        if found:
            return found
    return _FALLBACK_NAMESPACES

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
    """Infer the plugin name from a file path by looking for a ``plugins/<ns>`` segment."""
    parts = path.parts
    for i, part in enumerate(parts):
        if part == "plugins" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _discover_agents(
    name: str, namespace: str | None, root: Path
) -> list[AgentDetail]:
    """Core discovery algorithm shared by ``discover`` and ``info``.

    Search order:
    1. Registry exact match (case-insensitive), filtered by namespace
    2. Registry substring match (case-insensitive)
    3. Filesystem fallback -- glob ``plugins/{ns-or-*}/agents/*.md``
    """
    registry = load_registry(root)
    agents_section = registry.get("agents", {})
    name_lower = name.lower()

    if agents_section:
        # --- Step 1: exact match in registry keys ---
        exact: list[AgentDetail] = []
        for key, entry in agents_section.items():
            if namespace is not None and entry.get("plugin", "") != namespace:
                continue
            if key.lower() == name_lower:
                agent_path = resolve_agent_path(root, entry, key)
                if agent_path is not None:
                    detail = read_agent_file(agent_path)
                    if detail is not None:
                        exact.append(detail)
        if exact:
            return exact

        # --- Step 2: substring match in registry keys ---
        substring: list[AgentDetail] = []
        for key, entry in agents_section.items():
            if namespace is not None and entry.get("plugin", "") != namespace:
                continue
            if name_lower in key.lower():
                agent_path = resolve_agent_path(root, entry, key)
                if agent_path is not None:
                    detail = read_agent_file(agent_path)
                    if detail is not None:
                        substring.append(detail)
        if substring:
            return substring

    # --- Step 3: filesystem fallback ---
    namespaces = (namespace,) if namespace else _discover_namespaces(root)
    fs_matches: list[AgentDetail] = []
    for ns in namespaces:
        agents_dir = root / "plugins" / ns / "agents"
        if not agents_dir.is_dir():
            continue
        for md_file in sorted(agents_dir.glob("*.md")):
            stem_lower = md_file.stem.lower()
            if stem_lower == name_lower or name_lower in stem_lower:
                detail = read_agent_file(md_file)
                if detail is not None:
                    fs_matches.append(detail)
    return fs_matches


def _first_paragraph(body: str) -> str:
    """Extract the first paragraph from an agent body.

    Skips heading lines (starting with ``#``) and blank lines, then
    collects consecutive non-blank, non-heading lines.  Stops at the
    next blank line or heading.
    """
    lines = body.splitlines()
    paragraph_lines: list[str] = []
    collecting = False

    for line in lines:
        stripped = line.strip()
        if not collecting:
            # Skip headings and blank lines before the paragraph
            if not stripped or stripped.startswith("#"):
                continue
            collecting = True
            paragraph_lines.append(line)
        else:
            # Stop at blank line or heading
            if not stripped or stripped.startswith("#"):
                break
            paragraph_lines.append(line)

    return "\n".join(paragraph_lines)


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
    namespaces = (namespace,) if namespace else _discover_namespaces(root)
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
    name: Annotated[
        str,
        typer.Argument(help="Agent name or substring to search for."),
    ],
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Filter by plugin namespace."),
    ] = None,
) -> None:
    """Discover agents matching a name query."""
    root = get_root()
    matches = _discover_agents(name, namespace, root)

    if len(matches) == 1:
        emit(DiscoverResult(found=True, agent=matches[0]))
    elif len(matches) > 1:
        emit(DiscoverResult(found=False, matches=matches))
    else:
        emit(DiscoverResult(found=False, matches=[]))


@app.command()
def info(
    name: Annotated[
        str,
        typer.Argument(help="Agent name to look up."),
    ],
    namespace: Annotated[
        Optional[str],
        typer.Option("--namespace", "-n", help="Filter by plugin namespace."),
    ] = None,
) -> None:
    """Show detailed info for a specific agent (first paragraph only)."""
    root = get_root()
    matches = _discover_agents(name, namespace, root)

    if len(matches) == 1:
        agent = matches[0].model_copy()
        agent.body = _first_paragraph(agent.body)
        emit(DiscoverResult(found=True, agent=agent))
    elif len(matches) > 1:
        for m in matches:
            m.body = _first_paragraph(m.body)
        emit(DiscoverResult(found=False, matches=matches))
    else:
        emit(DiscoverResult(found=False, matches=[]))


@app.command()
def validate(
    path: Annotated[
        str,
        typer.Argument(help="Path to the agent .md file to validate."),
    ],
) -> None:
    """Validate an agent file for required structure."""
    errors: list[str] = []
    file_path = Path(path)

    if not file_path.exists():
        errors.append(f"File does not exist: {path}")
        emit(ValidateResult(valid=False, errors=errors))
        return

    content = file_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(content)

    if not meta:
        errors.append("Missing or invalid YAML frontmatter (must start with ---)")

    if meta and "description" not in meta:
        errors.append("Frontmatter missing required 'description' field")

    if not body.strip():
        errors.append("Body is empty (must have content after frontmatter)")

    emit(ValidateResult(valid=len(errors) == 0, errors=errors))


# ---------------------------------------------------------------------------
# State subcommands
# ---------------------------------------------------------------------------

_STALE_THRESHOLD = timedelta(hours=24)


def _state_file() -> Path:
    """Return the path to the session state file."""
    return get_state_dir() / "state.json"


def _is_stale(state: StateData | dict) -> bool:
    """Return True if state is stale.

    Primary check: compare ``session_id`` against the ``CLAUDE_SESSION_ID``
    environment variable (a mismatch means the state belongs to a different
    or crashed session).  Falls back to a 24-hour TTL if the env var is
    absent.
    """
    env_session = os.environ.get("CLAUDE_SESSION_ID")
    if isinstance(state, dict):
        session_id = state.get("session_id", "")
        loaded_at = state.get("loaded_at", "")
    else:
        session_id = state.session_id
        loaded_at = state.loaded_at

    # Primary: session ID mismatch
    if env_session and session_id and env_session != session_id:
        return True

    # Fallback: 24-hour TTL
    try:
        ts = datetime.fromisoformat(loaded_at)
        return datetime.now(timezone.utc) - ts > _STALE_THRESHOLD
    except (ValueError, TypeError):
        return True


@state_app.command("create")
def state_create(
    agent: Annotated[
        str,
        typer.Option("--agent", help="Agent name to activate."),
    ],
    plugin: Annotated[
        str,
        typer.Option("--plugin", help="Plugin the agent belongs to."),
    ],
    source: Annotated[
        str,
        typer.Option("--source", help="Path to the agent source file."),
    ],
) -> None:
    """Create a new agent session."""
    sd = get_state_dir()
    sd.mkdir(parents=True, exist_ok=True)

    state = StateData(
        active_agent=agent,
        plugin=plugin,
        source_file=source,
        loaded_at=datetime.now(timezone.utc).isoformat(),
        session_id=str(uuid.uuid4()),
    )

    sf = sd / "state.json"
    sf.write_text(state.model_dump_json(), encoding="utf-8")
    print(json.dumps({"created": True, "path": str(sf)}))


@state_app.command("check")
def state_check() -> None:
    """Check current agent session state."""
    sf = _state_file()
    if not sf.exists():
        emit(StateCheckResult(active=False))
        return

    try:
        raw = json.loads(sf.read_text(encoding="utf-8"))
        data = StateData(**raw)
        stale = _is_stale(data)
        emit(StateCheckResult(active=True, agent=data, stale=stale))
    except (json.JSONDecodeError, TypeError, KeyError):
        emit(StateCheckResult(active=False))


@state_app.command("clean")
def state_clean(
    if_stale: Annotated[
        bool,
        typer.Option("--if-stale", help="Only clean if state is stale (>24h)."),
    ] = False,
) -> None:
    """Clean up stale session state."""
    sf = _state_file()
    if not sf.exists():
        print(json.dumps({"cleaned": False}))
        return

    if if_stale:
        try:
            raw = json.loads(sf.read_text(encoding="utf-8"))
            if not _is_stale(raw):
                print(json.dumps({"cleaned": False}))
                return
        except (json.JSONDecodeError, TypeError):
            pass  # corrupt state -> treat as stale, remove it

    sf.unlink()
    print(json.dumps({"cleaned": True}))


@state_app.command("reminder")
def state_reminder() -> None:
    """Emit a compact persona reminder for PreCompact injection."""
    sf = _state_file()
    if not sf.exists():
        print(json.dumps({"active": False, "reminder": ""}))
        return

    try:
        raw = json.loads(sf.read_text(encoding="utf-8"))
        data = StateData(**raw)
    except (json.JSONDecodeError, TypeError, KeyError):
        print(json.dumps({"active": False, "reminder": ""}))
        return

    reminder = (
        f"=== AGENT SESSION REMINDER (post-compaction) ===\n"
        f"You are currently operating as {data.active_agent} ({data.plugin} plugin).\n"
        f"Full behavioral instructions were loaded earlier in this session.\n"
        f"Maintain this persona. These instructions take precedence over\n"
        f"other persona guidance. Project conventions and safety constraints\n"
        f"remain in effect.\n"
        f"=== END REMINDER ==="
    )
    print(json.dumps({"active": True, "reminder": reminder}))


@state_app.command("delete")
def state_delete() -> None:
    """Delete the current agent session."""
    sf = _state_file()
    if sf.exists():
        sf.unlink()
        print(json.dumps({"deleted": True}))
    else:
        print(json.dumps({"deleted": False}))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
