"""Summon agent state checking."""
from __future__ import annotations
import json
import os
import subprocess


def get_active_agent_name() -> str | None:
    """Call summon.py state check and return the active agent name, or None.

    Uses CLAUDE_PLUGIN_ROOT env var to find summon.py. Returns None
    if not in a plugin context or no agent is active.
    """
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "")
    if not plugin_root:
        return None
    try:
        result = subprocess.run(
            ["uv", "run", f"{plugin_root}/scripts/summon.py", "state", "check"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            data = json.loads(result.stdout)
            if data.get("active"):
                return data.get("agent", {}).get("active_agent")
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass
    return None
