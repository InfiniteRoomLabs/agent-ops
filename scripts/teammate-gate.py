# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Validate subagent output on TeammateIdle and TaskCompleted hooks.

Discovers changed files via ``git status --porcelain`` and runs encoding,
env-file, and agent-directory checks.

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
from _shared.encoding import find_encoding_artifacts  # noqa: E402
from frontmatter_config import resolve_typed  # noqa: E402
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
            chars_desc = ", ".join(f"U+{ord(c):04X}" for c in sorted(found))
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


def _payload_cwd() -> Path:
    """Read the hook's stdin JSON payload and return its ``cwd``.

    Teammates run in worktrees: validating the PROCESS cwd inspects the wrong
    tree (security checks silently bypassed, or a clean teammate blocked for
    other people's files). Missing/malformed payloads fall back to the
    process cwd.
    """
    try:
        payload = json.loads(sys.stdin.read())
        raw = payload.get("cwd", "") if isinstance(payload, dict) else ""
        if raw:
            return Path(raw)
    except Exception:
        pass
    return Path.cwd()


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


def _validate(cwd: Path) -> None:
    """Run all configured checks against the tree at ``cwd`` and exit."""
    config = resolve_typed(EnforcementConfig, "enforcement", cwd=cwd)

    if not config.teammate_validation:
        raise typer.Exit(0)

    rel_files = _get_changed_files(cwd)
    if not rel_files:
        raise typer.Exit(0)

    # Absolute paths for checks that read file contents / report locations;
    # repo-relative paths for the agent-dir check so directory components of
    # the worktree's own location can never false-match AGENT_DIRS.
    abs_files = [cwd / f for f in rel_files]

    all_violations: list[dict] = []
    for check_name in config.teammate_checks:
        check_fn = CHECK_REGISTRY.get(check_name)
        if check_fn is not None:
            target = rel_files if check_name == "agent_dirs" else abs_files
            all_violations.extend(check_fn(target))

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
    _validate(_payload_cwd())


@app.command()
def completed() -> None:
    """TaskCompleted hook entry point. Reads JSON payload from stdin."""
    _validate(_payload_cwd())


if __name__ == "__main__":
    app()
