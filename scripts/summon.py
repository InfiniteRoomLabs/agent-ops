# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""SUMMON -- agent discovery, inspection, and session management CLI.

Usage:
  uv run summon.py [--root PATH] [--state-dir PATH] <command> [options]
"""

from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).parent))
from _shared.paths import cwd_slug  # noqa: E402

import typer
import yaml
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).resolve().parent
PLUGIN_ROOT = SCRIPT_DIR.parent  # agent-ops repo root (scripts/ is one level deep)
DEFAULT_AGENT_OPS_ROOT = PLUGIN_ROOT  # agent-ops repo root

_FALLBACK_DIVISIONS = (
    "core",
    "design",
    "engineering",
    "game-development",
    "marketing",
    "paid-media",
    "product",
    "project-management",
    "research",
    "sales",
    "spatial-computing",
    "specialized",
    "support",
    "testing",
)


def _discover_divisions(root: Path) -> tuple[str, ...]:
    """Dynamically discover agent divisions from ``agents/*/`` directories.

    Falls back to a hardcoded tuple if the agents directory doesn't exist.
    """
    agents_dir = root / "agents"
    if agents_dir.is_dir():
        found = tuple(
            sorted(d.name for d in agents_dir.iterdir() if d.is_dir())
        )
        if found:
            return found
    return _FALLBACK_DIVISIONS

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

    Default: derive from the project directory using Claude Code's project
    memory path pattern -- ``~/.claude/projects/-{slug}/memory/summon/``
    where *slug* is the project dir with ``/`` replaced by ``-``.

    Prefers ``CLAUDE_PROJECT_DIR`` (the session's project root) over the
    live process cwd: hooks and subshells can run from subdirectories or
    worktrees, which would otherwise scatter state across multiple slugs.
    """
    if _state_dir_override is not None:
        return _state_dir_override

    slug = cwd_slug(os.environ.get("CLAUDE_PROJECT_DIR") or None)
    return Path.home() / ".claude" / "projects" / slug / "memory" / "summon"


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class AgentSummary(BaseModel):
    name: str = ""
    division: str = ""
    description: str = ""
    model: str = ""
    color: str = ""


class AgentDetail(BaseModel):
    name: str = ""
    division: str = ""
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
    division: str = ""
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
    falls back to division-based conventional path.
    """
    # Try explicit registry path
    reg_path = registry_entry.get("path", "")
    if reg_path:
        candidate = root / f"{reg_path}.md"
        if candidate.exists():
            return candidate

    # Fallback: agents/<division>/<name>.md
    division = registry_entry.get("division", "")
    if division:
        candidate = root / "agents" / division / f"{name}.md"
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
        division=_infer_division(path),
        path=str(path),
        description=meta.get("description", ""),
        model=meta.get("model", ""),
        tools=meta.get("tools", ""),
        color=meta.get("color", ""),
        tags=meta.get("tags", {}),
        body=body,
    )


def _infer_division(path: Path) -> str:
    """Infer the division name from a file path by looking for an ``agents/<division>`` segment."""
    parts = path.parts
    for i, part in enumerate(parts):
        if part == "agents" and i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _discover_agents(
    name: str, division: str | None, root: Path
) -> list[AgentDetail]:
    """Core discovery algorithm shared by ``discover`` and ``info``.

    Search order:
    1. Registry exact match (case-insensitive), filtered by division
    2. Registry substring match (case-insensitive)
    3. Filesystem fallback -- glob ``agents/{div-or-*}/*.md``
    """
    registry = load_registry(root)
    agents_section = registry.get("agents", {})
    name_lower = name.lower()

    if agents_section:
        # --- Step 1: exact match in registry keys ---
        exact: list[AgentDetail] = []
        for key, entry in agents_section.items():
            if division is not None and entry.get("division", "") != division:
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
            if division is not None and entry.get("division", "") != division:
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
    divisions = (division,) if division else _discover_divisions(root)
    fs_matches: list[AgentDetail] = []
    for div in divisions:
        agents_dir = root / "agents" / div
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
    root: Path, agents_section: dict, division: str | None
) -> list[AgentSummary]:
    """Build agent summaries from the registry.yaml agents section."""
    summaries: list[AgentSummary] = []
    for name, entry in agents_section.items():
        # Apply division filter when requested
        if division is not None and entry.get("division", "") != division:
            continue

        agent_path = resolve_agent_path(root, entry, name)
        if agent_path is not None:
            detail = read_agent_file(agent_path)
            if detail is not None:
                summaries.append(
                    AgentSummary(
                        name=detail.name,
                        division=detail.division,
                        description=detail.description,
                        model=detail.model,
                        color=detail.color,
                    )
                )
            else:
                summaries.append(
                    AgentSummary(name=name, division=entry.get("division", ""))
                )
        else:
            summaries.append(
                AgentSummary(name=name, division=entry.get("division", ""))
            )
    return summaries


def _list_from_filesystem(
    root: Path, division: str | None
) -> list[AgentSummary]:
    """Scan the filesystem for agent .md files and build summaries."""
    summaries: list[AgentSummary] = []
    divisions = (division,) if division else _discover_divisions(root)
    for div in divisions:
        agents_dir = root / "agents" / div
        if not agents_dir.is_dir():
            continue
        for md_file in sorted(agents_dir.glob("*.md")):
            detail = read_agent_file(md_file)
            if detail is not None:
                summaries.append(
                    AgentSummary(
                        name=detail.name,
                        division=detail.division,
                        description=detail.description,
                        model=detail.model,
                        color=detail.color,
                    )
                )
    return summaries


@app.command(name="list")
def list_agents(
    division: Annotated[
        Optional[str],
        typer.Option("--division", "-d", help="Filter agents by division."),
    ] = None,
) -> None:
    """List all registered agents."""
    root = get_root()
    registry = load_registry(root)
    agents_section = registry.get("agents", {})

    if agents_section:
        summaries = _list_from_registry(root, agents_section, division)
    else:
        summaries = _list_from_filesystem(root, division)

    emit(ListResult(agents=summaries))


@app.command()
def discover(
    name: Annotated[
        str,
        typer.Argument(help="Agent name or substring to search for."),
    ],
    division: Annotated[
        Optional[str],
        typer.Option("--division", "-d", help="Filter by division."),
    ] = None,
) -> None:
    """Discover agents matching a name query."""
    root = get_root()
    matches = _discover_agents(name, division, root)

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
    division: Annotated[
        Optional[str],
        typer.Option("--division", "-d", help="Filter by division."),
    ] = None,
) -> None:
    """Show detailed info for a specific agent (first paragraph only)."""
    root = get_root()
    matches = _discover_agents(name, division, root)

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


def _atomic_write_text(path: Path, content: str) -> None:
    """Write `content` to `path` atomically (tmp file + os.replace).

    A reader (state check / reminder) can never observe a partially
    written state file, and a crash mid-write leaves the previous state
    intact.
    """
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


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
    division: Annotated[
        str,
        typer.Option("--division", help="Division the agent belongs to."),
    ],
    source: Annotated[
        str,
        typer.Option("--source", help="Path to the agent source file."),
    ],
) -> None:
    """Create a new agent session."""
    sd = get_state_dir()
    sd.mkdir(parents=True, exist_ok=True)

    # Use the live session's ID when available (per the implementation plan):
    # a random UUID here would NEVER match CLAUDE_SESSION_ID at check time,
    # making every state file instantly "stale" -- SessionStart clean would
    # delete live personas.
    session_id = os.environ.get("CLAUDE_SESSION_ID") or str(uuid.uuid4())

    state = StateData(
        active_agent=agent,
        division=division,
        source_file=source,
        loaded_at=datetime.now(timezone.utc).isoformat(),
        session_id=session_id,
    )

    sf = sd / "state.json"
    _atomic_write_text(sf, state.model_dump_json())
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
        f"You are currently operating as {data.active_agent} ({data.division} division).\n"
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
