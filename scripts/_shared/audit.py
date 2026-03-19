"""Generic JSONL audit logging."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path


def write_audit_entry(
    audit_dir: Path,
    log_name: str,
    entry: dict,
    *,
    add_timestamp: bool = True,
) -> None:
    """Append a JSON object as a line to {audit_dir}/{log_name}.jsonl.

    Args:
        audit_dir: Directory to write to (created if missing)
        log_name: Filename without extension (e.g., "stop-failures")
        entry: Dict to serialize as JSON
        add_timestamp: If True, adds "timestamp" key with UTC ISO 8601
    """
    audit_dir.mkdir(parents=True, exist_ok=True)
    if add_timestamp and "timestamp" not in entry:
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), **entry}
    with (audit_dir / f"{log_name}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
