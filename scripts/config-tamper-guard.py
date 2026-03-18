# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Config tamper guard for Claude Code ConfigChange hook.

Two-phase design:
  - ``snapshot`` subcommand: cache current settings.json at SessionStart
  - ``hook`` subcommand: diff against cache on ConfigChange, block if protected
    keys were removed or weakened

Blocking format follows ConfigChange convention -- JSON decision on stdout:
  Allow:  exit 0, no output
  Block:  exit 0, ``{"decision": "block", "reason": "..."}`` on stdout
  Error:  exit 2 fallback
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_typed  # noqa: E402

import typer
from pydantic import BaseModel, Field

app = typer.Typer(
    help="Guard against tampering with protected settings.json keys.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Config model
# ---------------------------------------------------------------------------


class EnforcementConfig(BaseModel):
    protected_settings: list[str] = Field(
        default_factory=lambda: ["hooks", "permissions.deny"]
    )


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def _resolve_dotted(data: dict, dotted_key: str) -> Any:
    """Resolve a dotted key path like ``permissions.deny`` in a nested dict.

    Returns ``None`` if any segment is missing.
    """
    current: Any = data
    for segment in dotted_key.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None
        current = current[segment]
    return current


def snapshot_settings(
    *,
    settings_path: Path | None = None,
    cache_dir: Path | None = None,
) -> None:
    """Cache ``settings.json`` for later comparison."""
    if settings_path is None:
        settings_path = Path.cwd() / ".claude" / "settings.json"

    if cache_dir is None:
        slug = str(Path.cwd()).replace("/", "-")
        cache_dir = Path.home() / ".claude" / "projects" / slug / "memory" / "audit"

    if not settings_path.is_file():
        return

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "settings-snapshot.json"
    cache_file.write_text(settings_path.read_text())


def detect_tamper(
    before: dict,
    after: dict,
    protected_keys: list[str],
) -> dict:
    """Compare *before* and *after* settings for protected-key tampering.

    Returns ``{"tampered": bool, "reasons": [...]}``.

    Tamper conditions per protected key:
      - Key removed (was present, now None)
      - List value weakened (items removed)
      - Dict value lost sub-keys
    """
    reasons: list[str] = []

    for key in protected_keys:
        old_val = _resolve_dotted(before, key)
        new_val = _resolve_dotted(after, key)

        if old_val is None:
            # Key wasn't present before -- nothing to protect
            continue

        if new_val is None:
            reasons.append(f"Protected key '{key}' was removed")
            continue

        # List weakened -- items removed
        if isinstance(old_val, list) and isinstance(new_val, list):
            removed = set(old_val) - set(new_val)
            if removed:
                reasons.append(
                    f"Protected key '{key}' was weakened: removed {sorted(removed)}"
                )
            continue

        # Dict lost sub-keys
        if isinstance(old_val, dict) and isinstance(new_val, dict):
            lost = set(old_val.keys()) - set(new_val.keys())
            if lost:
                reasons.append(
                    f"Protected key '{key}' lost sub-keys: {sorted(lost)}"
                )
            continue

    return {"tampered": bool(reasons), "reasons": reasons}


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@app.command()
def snapshot() -> None:
    """Cache current settings.json at SessionStart."""
    snapshot_settings()
    raise typer.Exit(0)


@app.command()
def hook() -> None:
    """ConfigChange hook entry point. Reads new settings from stdin."""
    try:
        config = resolve_typed(
            model=EnforcementConfig,
            namespace="enforcement",
        )

        # Locate cached snapshot
        slug = str(Path.cwd()).replace("/", "-")
        cache_dir = (
            Path.home() / ".claude" / "projects" / slug / "memory" / "audit"
        )
        cache_file = cache_dir / "settings-snapshot.json"

        if not cache_file.is_file():
            # No snapshot to compare against -- allow
            raise typer.Exit(0)

        before = json.loads(cache_file.read_text())

        # Read the new settings from stdin (ConfigChange payload)
        raw = sys.stdin.read().strip()
        if not raw:
            raise typer.Exit(0)

        payload = json.loads(raw)
        after = payload if isinstance(payload, dict) else {}

        result = detect_tamper(before, after, config.protected_settings)

        if result["tampered"]:
            decision = {
                "decision": "block",
                "reason": "; ".join(result["reasons"]),
            }
            typer.echo(json.dumps(decision))

        # Update snapshot to current state for future comparisons
        cache_file.write_text(json.dumps(after, indent=2))

    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        typer.echo(f"config-tamper-guard error: {exc}", err=True)
        raise typer.Exit(2) from exc

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
