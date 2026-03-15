# /// script
# dependencies = ["pyyaml"]
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
import os
import re
import sys
from pathlib import Path

import yaml


FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

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


def parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content."""
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None
    try:
        return yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None


def find_claude_md_files() -> list[Path]:
    """Find CLAUDE.md files: global first, then project hierarchy (most general first)."""
    files = []

    # Global user config
    global_md = Path.home() / ".claude" / "CLAUDE.md"
    if global_md.is_file():
        files.append(global_md)

    # Walk up from CWD collecting CLAUDE.md files (child -> parent order)
    project_files = []
    seen = set()
    current = Path.cwd().resolve()
    home = Path.home().resolve()

    while current != current.parent and current != home:
        candidate = current / "CLAUDE.md"
        resolved = candidate.resolve()
        if candidate.is_file() and resolved not in seen:
            seen.add(resolved)
            project_files.append(candidate)
        current = current.parent

    # Reverse so most general (parent) comes first, most specific (CWD) last
    # This way project-level settings override parent settings
    files.extend(reversed(project_files))

    return files


def extract_adhd_config(files: list[Path]) -> dict | None:
    """Extract and merge accessibility.adhd config from CLAUDE.md files.

    Files are processed in order (global -> parent -> project).
    Later entries override earlier ones, so project-level config wins.
    """
    merged = None

    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        frontmatter = parse_frontmatter(content)
        if not frontmatter:
            continue

        accessibility = frontmatter.get("accessibility")
        if not isinstance(accessibility, dict):
            continue

        adhd = accessibility.get("adhd")
        if not isinstance(adhd, dict):
            continue

        if merged is None:
            merged = {**DEFAULT_ADHD_CONFIG, **adhd}
        else:
            merged.update(adhd)

    return merged


def main():
    check_only = "--check" in sys.argv

    files = find_claude_md_files()
    config = extract_adhd_config(files)

    if config is None or not config.get("enabled", False):
        if check_only:
            sys.exit(1)
        return

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
