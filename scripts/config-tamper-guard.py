# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Config tamper guard for Claude Code ConfigChange hook.

Design (reworked 2026-06-11 against the official ConfigChange spec):

  - The ConfigChange payload is a METADATA ENVELOPE (config_source,
    changed_keys, file_path) -- it does NOT carry the new settings content.
    The hook reads the new content fresh from ``file_path``.
  - Snapshots are kept PER SOURCE (user_settings / project_settings /
    local_settings) so a local-settings change is never diffed against a
    project-settings baseline.
  - ConfigChange fires AFTER the write, but blocking (exit 2 or a
    ``{"decision": "block"}`` JSON decision) makes Claude Code REVERT the
    change. Therefore: on block the snapshot is NOT updated -- the reverted
    file still matches the baseline. Only allowed changes advance it.
  - Failure policy is FAIL-CLOSED: if the hook cannot evaluate a change
    (malformed payload, unreadable/invalid settings file), it blocks via
    exit 2 and the change is reverted.

Tamper conditions:
  - Anything removed or modified under a protected key, at any depth
    (additions are always allowed -- protected subtrees are append-only).
  - A blocked key (kill-switch denylist, e.g. ``disableAllHooks``) turning
    truthy.

Two-phase wiring:
  - ``snapshot`` subcommand: cache each settings source at SessionStart
  - ``hook`` subcommand: diff the changed source against its snapshot on
    ConfigChange
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared.audit import write_audit_entry  # noqa: E402
from _shared.dotted import resolve_dotted  # noqa: E402
from _shared.paths import get_audit_dir, project_dir  # noqa: E402
from frontmatter_config import resolve_typed  # noqa: E402

import typer
from pydantic import BaseModel, Field

app = typer.Typer(
    help="Guard against tampering with protected settings keys.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Config + payload models
# ---------------------------------------------------------------------------


class EnforcementConfig(BaseModel):
    protected_settings: list[str] = Field(
        default_factory=lambda: ["hooks", "permissions.deny"]
    )
    # Dotted keys that must never turn truthy (kill-switch denylist).
    blocked_settings: list[str] = Field(
        default_factory=lambda: ["disableAllHooks"]
    )


class ConfigChangePayload(BaseModel):
    config_source: str = ""
    changed_keys: list[str] = Field(default_factory=list)
    file_path: str = ""
    cwd: str = ""


# Sources we snapshot and judge, mapped to their on-disk settings file.
# policy_settings is unblockable by user hooks; skills files are markdown,
# not JSON settings -- both fall through to the audit-only path in hook().
SOURCE_FILES: dict[str, Callable[[Path], Path]] = {
    "user_settings": lambda _cwd: Path.home() / ".claude" / "settings.json",
    "project_settings": lambda cwd: cwd / ".claude" / "settings.json",
    "local_settings": lambda cwd: cwd / ".claude" / "settings.local.json",
}


def snapshot_path(cache_dir: Path, source: str) -> Path:
    return cache_dir / f"settings-snapshot-{source}.json"


# ---------------------------------------------------------------------------
# Core logic
# ---------------------------------------------------------------------------


def snapshot_settings(
    *,
    cwd: Path | None = None,
    cache_dir: Path | None = None,
) -> None:
    """Cache every existing settings source for later comparison."""
    cwd = cwd or project_dir()
    cache_dir = cache_dir or get_audit_dir(cwd)
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Pre-rework versions kept a single combined snapshot; drop it so it
    # never lingers looking authoritative next to the per-source files.
    (cache_dir / "settings-snapshot.json").unlink(missing_ok=True)

    for source, locate in SOURCE_FILES.items():
        path = locate(cwd)
        if path.is_file():
            snapshot_path(cache_dir, source).write_text(
                path.read_text(encoding="utf-8"), encoding="utf-8"
            )


def _canon(value: object) -> str:
    """Canonical JSON form so list items (incl. dicts) are comparable."""
    return json.dumps(value, sort_keys=True)


def find_weakenings(old: object, new: object, path: str) -> list[str]:
    """Recursively find removals/modifications going old -> new.

    Additions are allowed at every level; protected subtrees are
    effectively append-only. Returns human-readable reason strings.
    """
    if old == new:
        return []

    if isinstance(old, dict) and isinstance(new, dict):
        reasons: list[str] = []
        for key, old_val in old.items():
            child = f"{path}.{key}"
            if key not in new:
                reasons.append(f"'{child}' was removed")
            else:
                reasons.extend(find_weakenings(old_val, new[key], child))
        return reasons

    if isinstance(old, list) and isinstance(new, list):
        removed = Counter(map(_canon, old)) - Counter(map(_canon, new))
        if removed:
            return [f"'{path}' lost items: {sorted(removed)}"]
        return []

    return [f"'{path}' was modified: {_canon(old)} -> {_canon(new)}"]


def detect_tamper(
    before: dict,
    after: dict,
    protected_keys: list[str],
    blocked_keys: list[str] | None = None,
) -> list[str]:
    """Compare *before* and *after* settings for tampering.

    Returns the (possibly empty) list of tamper reasons.
    """
    reasons: list[str] = []

    for key in protected_keys:
        old_val = resolve_dotted(before, key)
        if old_val is None:
            continue  # key wasn't present before -- nothing to protect
        new_val = resolve_dotted(after, key)
        if new_val is None:
            reasons.append(f"Protected key '{key}' was removed")
            continue
        reasons.extend(
            f"Protected key {r}" for r in find_weakenings(old_val, new_val, key)
        )

    for key in blocked_keys or []:
        new_val = resolve_dotted(after, key)
        if new_val and not resolve_dotted(before, key):
            reasons.append(f"Blocked key '{key}' was enabled (now {_canon(new_val)})")

    return reasons


# ---------------------------------------------------------------------------
# Hook evaluation (pure-ish core, injected paths)
# ---------------------------------------------------------------------------


def evaluate_change(
    payload: ConfigChangePayload,
    config: EnforcementConfig,
    cache_dir: Path,
) -> tuple[bool, str]:
    """Judge one ConfigChange. Returns (allowed, reason).

    A missing snapshot means the file was born mid-session: the empty
    baseline lets any content through the protected-key check (nothing
    existed to weaken) while the blocked-key check still applies.

    Side effects: advances the per-source snapshot on allow (never on
    block -- Claude Code reverts the file, so the baseline stays true).
    Raises on unreadable/invalid settings content (caller fails closed).
    """
    changed = Path(payload.file_path)
    raw = changed.read_text(encoding="utf-8") if changed.is_file() else "{}"
    after = json.loads(raw)
    if not isinstance(after, dict):
        raise TypeError(f"settings content is not a JSON object: {payload.file_path}")

    snap = snapshot_path(cache_dir, payload.config_source)
    before = json.loads(snap.read_text(encoding="utf-8")) if snap.is_file() else {}

    reasons = detect_tamper(
        before, after, config.protected_settings, config.blocked_settings
    )
    if reasons:
        return False, "; ".join(reasons)

    snap.write_text(raw, encoding="utf-8")
    return True, "no tampering detected"


# ---------------------------------------------------------------------------
# CLI commands
# ---------------------------------------------------------------------------


@app.command()
def snapshot() -> None:
    """Cache all settings sources at SessionStart."""
    snapshot_settings()


@app.command()
def hook() -> None:
    """ConfigChange hook entry point. Reads the metadata envelope from stdin.

    Fail-closed: any evaluation error exits 2, which reverts the change.
    """
    try:
        payload = ConfigChangePayload.model_validate_json(sys.stdin.read())
        cache_dir = get_audit_dir(project_dir(payload.cwd))

        if payload.config_source not in SOURCE_FILES:
            # policy_settings (unblockable), skills (not JSON settings),
            # or a future source we don't model: audit and allow.
            write_audit_entry(
                cache_dir,
                "config-changes",
                {
                    "event": "config_change_unjudged",
                    "config_source": payload.config_source,
                    "file_path": payload.file_path,
                    "changed_keys": payload.changed_keys,
                },
            )
            return

        config = resolve_typed(model=EnforcementConfig, namespace="enforcement")
        allowed, reason = evaluate_change(payload, config, cache_dir)

        if not allowed:
            write_audit_entry(
                cache_dir,
                "config-changes",
                {
                    "event": "config_change_blocked",
                    "config_source": payload.config_source,
                    "file_path": payload.file_path,
                    "changed_keys": payload.changed_keys,
                    "reason": reason,
                },
            )
            typer.echo(json.dumps({"decision": "block", "reason": reason}))

    except Exception as exc:  # fail-closed: unevaluated change gets reverted
        typer.echo(f"config-tamper-guard error (change reverted): {exc}", err=True)
        raise typer.Exit(2) from exc


if __name__ == "__main__":
    app()
