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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared.audit import write_audit_entry  # noqa: E402
from _shared.paths import get_audit_dir  # noqa: E402
from _shared.summon_state import get_active_agent_name  # noqa: E402
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
# Audit
# ---------------------------------------------------------------------------


def _write_audit(cwd: str, session_id: str, warnings: list[str]) -> None:
    """Write a JSONL audit entry for this compaction check."""
    audit_dir = get_audit_dir(cwd)
    write_audit_entry(
        audit_dir,
        "compaction-checks",
        {
            "session_id": session_id,
            "cwd": cwd,
            "warning_count": len(warnings),
            "warnings": warnings,
        },
    )


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
    agent_name = get_active_agent_name()

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
