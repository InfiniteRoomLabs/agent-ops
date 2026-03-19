# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Fire-and-forget JSONL audit logging when sessions crash.

StopFailure hook -- all output channels (exit, stdout, stderr) are ignored
by protocol.  This script simply appends a structured JSONL entry and exits 0.

Usage:
  echo '{"session_id":"...","cwd":"...","error":"...","error_details":"..."}' | \
    uv run stop-failure-audit.py hook
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed  # noqa: E402

import typer
from pydantic import BaseModel

app = typer.Typer(
    help="Audit logger for StopFailure hook events.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Config model (frontmatter namespace: audit)
# ---------------------------------------------------------------------------


class AuditConfig(BaseModel):
    stop_failures: bool = True
    log_path: str | None = None


# ---------------------------------------------------------------------------
# Hook payload
# ---------------------------------------------------------------------------


class HookPayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    error: str = ""
    error_details: str = ""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def write_failure_audit(
    *,
    audit_dir: Path,
    error: str,
    error_details: str,
    session_id: str,
    cwd: str,
    agent_name: str | None,
) -> None:
    """Append JSONL entry with timestamp, error, error_details, session_id, cwd, agent_name."""
    audit_dir.mkdir(parents=True, exist_ok=True)
    log_file = audit_dir / "stop-failures.jsonl"

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error": error,
        "error_details": error_details,
        "session_id": session_id,
        "cwd": cwd,
        "agent_name": agent_name,
    }

    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Agent check (same pattern as postcompact-recovery)
# ---------------------------------------------------------------------------


def _get_agent_name() -> str | None:
    """Call summon.py state check to get the active agent name, if any."""
    try:
        result = subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve().parent / "summon.py"),
                "state",
                "check",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        if data.get("active") and data.get("agent"):
            return data["agent"].get("active_agent") or None
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None


# ---------------------------------------------------------------------------
# Hook command
# ---------------------------------------------------------------------------


@app.command()
def hook() -> None:
    """StopFailure hook entry point. Reads JSON from stdin, writes audit log."""
    try:
        payload = HookPayload.model_validate_json(sys.stdin.read())
    except Exception:
        raise typer.Exit(0)

    # Check config
    try:
        config = resolve_typed(AuditConfig, "audit", cwd=Path(payload.cwd) if payload.cwd else None)
    except Exception:
        config = AuditConfig()

    if not config.stop_failures:
        raise typer.Exit(0)

    # Determine audit directory
    if config.log_path:
        audit_dir = Path(config.log_path).expanduser()
    else:
        slug = payload.cwd.replace("/", "-")
        audit_dir = Path.home() / ".claude" / "projects" / slug / "memory" / "audit"

    # Get active agent name
    agent_name = _get_agent_name()

    # Write audit entry -- fire and forget
    try:
        write_failure_audit(
            audit_dir=audit_dir,
            error=payload.error,
            error_details=payload.error_details,
            session_id=payload.session_id,
            cwd=payload.cwd,
            agent_name=agent_name,
        )
    except Exception:
        pass  # fire-and-forget: never fail

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
