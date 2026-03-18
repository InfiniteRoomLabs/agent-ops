# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""PostCompact recovery hook -- verify critical context survived compaction.

PostCompact stdout is NOT injected into context -- it surfaces as a
model-visible warning only via systemMessage.

Usage (hook):
    Reads JSON from stdin, checks compaction summary, writes audit JSONL,
    and outputs a systemMessage to stdout if warnings are found.
    Always exits 0.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed  # noqa: E402

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Config model (from CLAUDE.md frontmatter, "compaction" namespace)
# ---------------------------------------------------------------------------


class CompactionConfig(BaseModel):
    reinject: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Hook payload
# ---------------------------------------------------------------------------


class HookPayload(BaseModel):
    session_id: str = ""
    cwd: str = ""
    compact_summary: str = ""


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def check_compaction(
    *,
    compact_summary: str,
    reinject_strings: list[str],
    agent_name: str | None,
) -> dict:
    """Check whether critical context survived compaction.

    Returns {"warnings": [...]}.
    """
    warnings: list[str] = []

    if agent_name and agent_name.lower() not in compact_summary.lower():
        warnings.append(
            f"Agent persona '{agent_name}' not found in compaction summary. "
            "The agent identity may have been lost during compaction."
        )

    for s in reinject_strings:
        if s.lower() not in compact_summary.lower():
            warnings.append(
                f"Critical context '{s}' not found in compaction summary. "
                "This information may need to be re-established."
            )

    return {"warnings": warnings}


# ---------------------------------------------------------------------------
# Agent state check
# ---------------------------------------------------------------------------


def _get_active_agent_name() -> str | None:
    """Call summon.py state check to get the active agent name.

    Returns the agent name if active, None otherwise. Fails gracefully.
    """
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if not plugin_root:
        # Fallback: derive from this script's location
        plugin_root = str(Path(__file__).resolve().parent.parent)

    summon_path = Path(plugin_root) / "scripts" / "summon.py"
    if not summon_path.is_file():
        return None

    try:
        result = subprocess.run(
            ["uv", "run", str(summon_path), "state", "check"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout)
        if data.get("active") and data.get("agent"):
            return data["agent"].get("active_agent") or None
    except (json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        pass

    return None


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


def _write_audit(cwd: str, session_id: str, warnings: list[str]) -> None:
    """Write a JSONL audit entry for this compaction check."""
    slug = cwd.replace("/", "-")
    audit_dir = Path.home() / ".claude" / "projects" / slug / "memory" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)

    audit_file = audit_dir / "compaction-checks.jsonl"
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "session_id": session_id,
        "cwd": cwd,
        "warning_count": len(warnings),
        "warnings": warnings,
    }
    with open(audit_file, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Hook entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """PostCompact hook entry point. Reads JSON from stdin."""
    try:
        raw = sys.stdin.read()
        payload = HookPayload.model_validate_json(raw)
    except Exception:
        # Malformed input -- exit cleanly, never block
        sys.exit(0)

    # Load config from CLAUDE.md frontmatter
    cwd_path = Path(payload.cwd) if payload.cwd else Path.cwd()
    config = resolve_typed(
        model=CompactionConfig,
        namespace="compaction",
        cwd=cwd_path,
    )

    # Check for active agent
    agent_name = _get_active_agent_name()

    # Run the check
    result = check_compaction(
        compact_summary=payload.compact_summary,
        reinject_strings=config.reinject,
        agent_name=agent_name,
    )

    # Write audit
    _write_audit(
        cwd=payload.cwd or str(Path.cwd()),
        session_id=payload.session_id,
        warnings=result["warnings"],
    )

    # Output systemMessage if there are warnings
    if result["warnings"]:
        warning_text = (
            "=== POST-COMPACTION RECOVERY WARNING ===\n"
            + "\n".join(f"- {w}" for w in result["warnings"])
            + "\n=== END WARNING ==="
        )
        print(json.dumps({"systemMessage": warning_text}))

    sys.exit(0)


if __name__ == "__main__":
    main()
