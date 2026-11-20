# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Validate subagent output on TeammateIdle and TaskCompleted hooks.

Discovers changed files via ``git status --porcelain`` and runs encoding,
env-file, and agent-directory checks.

The encoding check (the only one that makes a teammate retry) is scoped to
the files the teammate itself wrote, read from its own transcript, so a
teammate is never sent back to fix files it did not touch -- possibly ones
it must not touch, which loops forever. The security checks keep judging
the whole changed tree. Without a locatable transcript, the encoding check
falls back to the whole changed tree too.

Exit behavior:
  - Clean:             exit 0, no output
  - Fixable violations (encoding): exit 2 + message on stderr (teammate retries)
  - Security violations (.env, agent dirs): exit 0 + JSON on stdout (hard stop)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import typer
from _shared.encoding import find_encoding_artifacts, format_artifact_codepoints  # noqa: E402
from _shared.frontmatter_config import resolve_typed  # noqa: E402
from pydantic import BaseModel, Field

app = typer.Typer(
    help="Validate subagent output for TeammateIdle / TaskCompleted hooks.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_DIRS = {
    ".claude",
    ".codex",
    ".gemini",
    ".cursor",
    ".qwen",
    ".opencode",
    ".windsurf",
    ".kilocode",
    ".augment",
    ".roo",
    ".amazonq",
}

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


class EnforcementConfig(BaseModel):
    teammate_validation: bool = True
    teammate_checks: list[str] = Field(
        default_factory=lambda: ["encoding", "env_files", "agent_dirs"]
    )


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------


def check_encoding(files: list[Path]) -> list[dict]:
    """Check .md files for problematic characters.

    Returns a list of violation dicts with keys:
      type, file, message, severity
    """
    violations: list[dict] = []
    for f in files:
        if f.suffix != ".md":
            continue
        try:
            content = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        found = find_encoding_artifacts(content)
        if found:
            chars_desc = format_artifact_codepoints(found)
            violations.append(
                {
                    "type": "encoding",
                    "file": str(f),
                    "message": f"Problematic characters found: {chars_desc}",
                    "severity": "fixable",
                }
            )
    return violations


def check_env_files(files: list[Path]) -> list[dict]:
    """Check for .env file creation.

    Returns a list of violation dicts with severity "security".
    """
    violations: list[dict] = []
    for f in files:
        if f.name == ".env" or f.name.startswith(".env."):
            violations.append(
                {
                    "type": "env_files",
                    "file": str(f),
                    "message": f"Environment file created or modified: {f.name}",
                    "severity": "security",
                }
            )
    return violations


def check_agent_dirs(files: list[Path]) -> list[dict]:
    """Check for files inside agent directories.

    Returns a list of violation dicts with severity "security".
    """
    violations: list[dict] = []
    for f in files:
        for part in f.parts:
            if part in AGENT_DIRS:
                violations.append(
                    {
                        "type": "agent_dirs",
                        "file": str(f),
                        "message": f"File in agent directory: {part}/",
                        "severity": "security",
                    }
                )
                break
    return violations


def classify_violations(
    violations: list[dict],
) -> tuple[list[dict], list[dict]]:
    """Split violations into (fixable, security) by severity field."""
    fixable = [v for v in violations if v["severity"] == "fixable"]
    security = [v for v in violations if v["severity"] == "security"]
    return fixable, security


# ---------------------------------------------------------------------------
# Shared validation logic
# ---------------------------------------------------------------------------

CHECK_REGISTRY: dict[str, type] = {
    "encoding": check_encoding,  # type: ignore[dict-item]
    "env_files": check_env_files,  # type: ignore[dict-item]
    "agent_dirs": check_agent_dirs,  # type: ignore[dict-item]
}


def _read_payload() -> dict:
    """The hook's stdin JSON payload; ``{}`` when missing or malformed."""
    try:
        payload = json.loads(sys.stdin.read())
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _payload_cwd(payload: dict) -> Path:
    """The payload's ``cwd``, else the process cwd.

    Teammates run in worktrees: validating the PROCESS cwd inspects the wrong
    tree (security checks silently bypassed, or a clean teammate blocked for
    other people's files).
    """
    raw = payload.get("cwd", "")
    return Path(raw) if isinstance(raw, str) and raw else Path.cwd()


# Tools whose calls write a file; NotebookEdit names it `notebook_path`.
WRITE_TOOLS = {"Edit", "MultiEdit", "Write", "NotebookEdit"}


def teammate_transcript(payload: dict) -> Path | None:
    """The teammate's own transcript, or None when it cannot be located.

    The payload's ``transcript_path`` is the SESSION's transcript even when
    the hook fires for a teammate; ``agent_id`` names the teammate. Claude
    Code (2.1.329) keeps the teammate's transcript at
    ``<session transcript without .jsonl>/subagents/agent-<agent_id>.jsonl``.
    That layout is observed, not documented, hence the None fallback.
    """
    session = payload.get("transcript_path")
    agent_id = payload.get("agent_id")
    if not (isinstance(session, str) and session and isinstance(agent_id, str) and agent_id):
        return None
    path = Path(session).with_suffix("") / "subagents" / f"agent-{agent_id}.jsonl"
    return path if path.is_file() else None


def files_edited_in_transcript(transcript: Path) -> list[Path]:
    """Files the agent wrote with Edit/Write/NotebookEdit, first-seen order,
    without duplicates. Unparseable lines are skipped."""
    seen: dict[str, None] = {}
    with transcript.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            message = record.get("message") if isinstance(record, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if not isinstance(content, list):
                continue
            for block in content:
                if not (
                    isinstance(block, dict)
                    and block.get("type") == "tool_use"
                    and block.get("name") in WRITE_TOOLS
                ):
                    continue
                tool_input = block.get("input")
                if not isinstance(tool_input, dict):
                    continue
                path = tool_input.get("file_path") or tool_input.get("notebook_path")
                if isinstance(path, str) and path:
                    seen.setdefault(path, None)
    return [Path(p) for p in seen]


def _get_changed_files(cwd: Path | None = None) -> list[Path]:
    """Discover changed files (repo-relative) for the repo at ``cwd``.

    Uses ``-z`` (NUL-separated, no quoting -- spaced/quoted paths survive)
    and ``--untracked-files=all`` (files inside new untracked directories
    are listed individually instead of as ``dir/``).
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        capture_output=True,
        text=True,
        cwd=cwd,
    )
    files: list[Path] = []
    fields = result.stdout.split("\0")
    i = 0
    while i < len(fields):
        entry = fields[i]
        i += 1
        if len(entry) < 4:
            continue
        status, path_part = entry[:2], entry[3:]
        files.append(Path(path_part))
        # Renames/copies: the ORIGINAL path follows as its own NUL field.
        if "R" in status or "C" in status:
            i += 1
    return files


def _validate(payload: dict) -> None:
    """Run all configured checks for the teammate described by ``payload``
    (against the tree at its ``cwd``) and exit."""
    cwd = _payload_cwd(payload)
    config = resolve_typed(EnforcementConfig, "enforcement", cwd=cwd)

    if not config.teammate_validation:
        raise typer.Exit(0)

    rel_files = _get_changed_files(cwd)

    # Absolute paths for checks that read file contents / report locations;
    # repo-relative paths for the agent-dir check so directory components of
    # the worktree's own location can never false-match AGENT_DIRS.
    abs_files = [cwd / f for f in rel_files]

    # The encoding check judges what the teammate wrote, wherever it wrote
    # it; the whole changed tree only when its transcript is not available.
    transcript = teammate_transcript(payload)
    encoding_files = (
        abs_files
        if transcript is None
        else [f for f in files_edited_in_transcript(transcript) if f.is_file()]
    )
    targets = {"agent_dirs": rel_files, "encoding": encoding_files}

    all_violations: list[dict] = []
    for check_name in config.teammate_checks:
        check_fn = CHECK_REGISTRY.get(check_name)
        if check_fn is not None:
            all_violations.extend(check_fn(targets.get(check_name, abs_files)))

    if not all_violations:
        raise typer.Exit(0)

    fixable, security = classify_violations(all_violations)

    # Security violations take precedence -- hard stop via stdout JSON
    if security:
        reasons = [v["message"] for v in security]
        payload = {
            "continue": False,
            "stopReason": "Security violation(s): " + "; ".join(reasons),
        }
        typer.echo(json.dumps(payload))
        raise typer.Exit(0)

    # Fixable violations -- exit 2 with message on stderr so teammate retries
    if fixable:
        messages = [f"  - {v['file']}: {v['message']}" for v in fixable]
        typer.echo(
            "Encoding violations found. Fix before continuing:\n"
            + "\n".join(messages),
            err=True,
        )
        raise typer.Exit(2)

    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Typer commands
# ---------------------------------------------------------------------------


@app.command()
def idle() -> None:
    """TeammateIdle hook entry point. Reads JSON payload from stdin."""
    _validate(_read_payload())


@app.command()
def completed() -> None:
    """TaskCompleted hook entry point. Reads JSON payload from stdin."""
    _validate(_read_payload())


if __name__ == "__main__":
    app()
