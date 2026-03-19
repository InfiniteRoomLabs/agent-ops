# /// script
# dependencies = ["pyyaml>=6"]
# ///
"""
Accessibility config detector for Claude Code.

Reads CLAUDE.md files (global and project-level), parses YAML frontmatter,
and outputs accessibility configuration if found. Used by the SessionStart
hook to auto-activate ADHD accessibility mode.

Usage:
    uv run accessibility-config.py [--check]

    --check: Exit 0 if config found and enabled, 1 if not (no output)
    (default): Output structured config as JSON if found, nothing if not
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from frontmatter_config import resolve_config  # noqa: E402

DEFAULT_ADHD_CONFIG = {
    "enabled": False,
    "micro_chunking": True,
    "reduced_decisions": True,
    "max_options": 2,
    "response_brevity": True,
    "max_prose_lines": 4,
    "momentum": True,
    "progress_dopamine": True,
    "context_anchoring": True,
    "anti_rabbit_hole": True,
    "time_awareness": True,
    "break_interval_minutes": 30,
    "sensory_friendly": True,
}

BEHAVIOR_LABELS = {
    "micro_chunking": "Micro-Chunking",
    "reduced_decisions": "Reduced Decision Points",
    "response_brevity": "Response Brevity",
    "momentum": "Momentum Preservation",
    "progress_dopamine": "Progress Dopamine",
    "context_anchoring": "Context Anchoring",
    "anti_rabbit_hole": "Anti-Rabbit-Hole Guardrails",
    "time_awareness": "Time Awareness",
    "sensory_friendly": "Sensory-Friendly Formatting",
}


def main():
    check_only = "--check" in sys.argv

    accessibility = resolve_config("accessibility")
    adhd = accessibility.get("adhd")

    if not isinstance(adhd, dict) or not adhd.get("enabled", False):
        if check_only:
            sys.exit(1)
        return

    config = {**DEFAULT_ADHD_CONFIG, **adhd}

    if check_only:
        sys.exit(0)

    enabled = []
    disabled = []

    for key, label in BEHAVIOR_LABELS.items():
        if config.get(key, True):
            enabled.append(label)
        else:
            disabled.append(label)

    output = {
        "accessibility_mode": "adhd",
        "auto_activated": True,
        "enabled_behaviors": enabled,
        "disabled_behaviors": disabled,
        "settings": {
            "max_options": config.get("max_options", 2),
            "max_prose_lines": config.get("max_prose_lines", 4),
            "break_interval_minutes": config.get("break_interval_minutes", 30),
        },
    }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
