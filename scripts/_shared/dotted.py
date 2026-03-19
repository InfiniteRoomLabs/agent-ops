"""Dotted key path traversal for nested dicts."""
from __future__ import annotations
from typing import Any


def resolve_dotted(data: dict, dotted_key: str) -> Any:
    """Traverse nested dict by dotted key path like 'permissions.deny'.

    Returns None if any segment is missing or data is not a dict at any level.
    """
    keys = dotted_key.split(".")
    current: Any = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current
