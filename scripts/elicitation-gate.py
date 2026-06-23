# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Gate for Elicitation and ElicitationResult hooks.

Audit-logs all MCP elicitation events and optionally blocks requests
whose serialized parameters match configured regex patterns.

Blocking uses hookSpecificOutput with action: "decline" on stdout (exit 0),
NOT exit 2.

Usage:
  Hook (request):  uv run elicitation-gate.py request  (reads JSON from stdin)
  Hook (result):   uv run elicitation-gate.py result   (reads JSON from stdin)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import typer
from pydantic import BaseModel, Field

# Ensure sibling modules are importable when invoked via uv run
sys.path.insert(0, str(Path(__file__).parent))
from _shared.audit import write_audit_entry  # noqa: E402
from _shared.paths import get_audit_dir  # noqa: E402
from _shared.frontmatter_config import resolve_typed  # noqa: E402

app = typer.Typer(
    help="Audit and optionally block MCP elicitation events.",
    no_args_is_help=True,
)


# -- Pydantic models --


class McpConfig(BaseModel):
    audit_elicitations: bool = True
    block_patterns: list[str] = Field(default_factory=list)


# -- Core functions --


def check_elicitation(
    *,
    server_name: str,
    request_type: str,
    parameters: dict,
    block_patterns: list[str],
) -> dict:
    """Check whether an elicitation request should be blocked.

    Returns {"blocked": bool, "matched_pattern": str}.
    Serializes the request as a JSON string, checks each pattern via
    re.search.  Skips invalid regex patterns silently.
    """
    serialized = json.dumps(
        {"server_name": server_name, "request_type": request_type, "parameters": parameters},
        sort_keys=True,
    )

    for pattern in block_patterns:
        try:
            if re.search(pattern, serialized):
                return {"blocked": True, "matched_pattern": pattern}
        except re.error:
            continue

    return {"blocked": False, "matched_pattern": ""}


def write_elicitation_audit(
    *,
    audit_dir: Path,
    event_type: str,
    server_name: str,
    details: dict,
) -> None:
    """Append a JSONL entry to elicitation-events.jsonl."""
    write_audit_entry(
        audit_dir,
        "elicitation-events",
        {
            "event_type": event_type,
            "server_name": server_name,
            **details,
        },
    )


# -- Typer commands --


def _emit_decline() -> None:
    """Decline via hookSpecificOutput on stdout (exit stays 0 per contract)."""
    typer.echo(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "Elicitation",
                    "action": "decline",
                }
            }
        )
    )


@app.command()
def request() -> None:
    """Elicitation hook: audit the request, block if patterns match."""
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("payload is not a JSON object")
    except Exception:
        # Unparseable payload: we cannot run the pattern check. If blocking
        # is configured, fail CLOSED (decline) -- a malformed payload must
        # not become a bypass. With no patterns configured, allow (exit 0),
        # matching the documented contract.
        cfg = resolve_typed(McpConfig, "mcp")
        if cfg.block_patterns:
            _emit_decline()
        raise typer.Exit(0)

    server_name = payload.get("server_name", "")
    request_type = payload.get("request_type", "")
    parameters = payload.get("parameters", {})

    cfg = resolve_typed(McpConfig, "mcp")

    # Audit
    if cfg.audit_elicitations:
        write_elicitation_audit(
            audit_dir=get_audit_dir(),
            event_type="elicitation_request",
            server_name=server_name,
            details={
                "request_type": request_type,
                "parameters": parameters,
            },
        )

    # Check block patterns
    result = check_elicitation(
        server_name=server_name,
        request_type=request_type,
        parameters=parameters,
        block_patterns=cfg.block_patterns,
    )

    if result["blocked"]:
        # Audit the block
        if cfg.audit_elicitations:
            write_elicitation_audit(
                audit_dir=get_audit_dir(),
                event_type="elicitation_blocked",
                server_name=server_name,
                details={
                    "matched_pattern": result["matched_pattern"],
                    "request_type": request_type,
                },
            )

        # Decline via hookSpecificOutput on stdout, exit 0
        _emit_decline()

    raise typer.Exit(0)


@app.command()
def result() -> None:
    """ElicitationResult hook: audit only."""
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            raise ValueError("payload is not a JSON object")
    except Exception:
        # Audit-only path: nothing to audit if we can't parse. Exit cleanly.
        raise typer.Exit(0)

    server_name = payload.get("server_name", "")
    result_data = payload.get("result", {})

    cfg = resolve_typed(McpConfig, "mcp")

    if cfg.audit_elicitations:
        write_elicitation_audit(
            audit_dir=get_audit_dir(),
            event_type="elicitation_result",
            server_name=server_name,
            details={"result": result_data},
        )

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
