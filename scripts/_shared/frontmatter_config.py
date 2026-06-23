# /// script
# dependencies = ["pyyaml>=6", "pydantic>=2"]
# ///
"""Shared CLAUDE.md frontmatter config library.

Parses YAML frontmatter from CLAUDE.md files, resolves them in hierarchy
order (global -> parent -> project), and optionally validates against
Pydantic models.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypeVar

import yaml

T = TypeVar("T")

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_frontmatter(content: str) -> dict | None:
    """Extract YAML frontmatter from markdown content.

    Returns the parsed dict, or None if no valid frontmatter is found.
    """
    match = FRONTMATTER_RE.match(content)
    if not match:
        return None
    try:
        result = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(result, dict):
        return None
    return result


def resolve_frontmatter(
    cwd: Path | None = None,
    home_override: Path | None = None,
) -> dict:
    """Walk the CLAUDE.md hierarchy and deep-merge all frontmatter.

    Resolution order (first applied, last wins):
      1. ``~/.claude/CLAUDE.md`` (global)
      2. Walk from *home* down to *cwd*, collecting intermediate CLAUDE.md files
      3. Most-specific (project-level) wins on conflicts

    Parameters
    ----------
    cwd:
        Working directory to resolve from.  Defaults to ``Path.cwd()``.
    home_override:
        Override for ``Path.home()`` -- used in tests to avoid touching the
        real filesystem.
    """
    if cwd is None:
        cwd = Path.cwd()
    cwd = cwd.resolve()

    files = find_claude_md_files(cwd, home_override=home_override)

    merged: dict = {}
    for path in files:
        try:
            content = path.read_text()
        except (OSError, PermissionError):
            continue
        fm = parse_frontmatter(content)
        if fm is not None:
            merged = _deep_merge(merged, fm)
    return merged


def resolve_config(
    namespace: str,
    cwd: Path | None = None,
    home_override: Path | None = None,
) -> dict:
    """Return a single top-level key from the merged frontmatter.

    Returns an empty dict if the namespace does not exist.
    """
    merged = resolve_frontmatter(cwd=cwd, home_override=home_override)
    value = merged.get(namespace, {})
    if not isinstance(value, dict):
        return {}
    return value


def resolve_typed(
    model: type[T],
    namespace: str,
    cwd: Path | None = None,
    home_override: Path | None = None,
) -> T:
    """Validate a namespace against a Pydantic BaseModel.

    Returns an instance of *model* populated from the merged frontmatter
    under *namespace*.  Missing keys fall back to model defaults.
    """
    raw = resolve_config(namespace=namespace, cwd=cwd, home_override=home_override)
    return model.model_validate(raw)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def find_claude_md_files(
    cwd: Path,
    home_override: Path | None = None,
) -> list[Path]:
    """Discover CLAUDE.md files in hierarchy order (general first).

    Order:
      1. Global: ``~/.claude/CLAUDE.md``
      2. Intermediate directories between home and cwd (outermost first)
      3. CWD's own ``CLAUDE.md``
    """
    home = (home_override or Path.home()).resolve()
    cwd = cwd.resolve()

    files: list[Path] = []

    # 1. Global
    global_md = home / ".claude" / "CLAUDE.md"
    if global_md.is_file():
        files.append(global_md)

    # 2. Walk from cwd upward to home, collecting CLAUDE.md files
    intermediate: list[Path] = []
    current = cwd
    while True:
        candidate = current / "CLAUDE.md"
        if candidate.is_file() and candidate != global_md:
            intermediate.append(candidate)
        if current == home or current == current.parent:
            break
        current = current.parent

    # Reverse so outermost parent comes first, project last
    intermediate.reverse()
    files.extend(intermediate)

    return files


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge *override* into *base*.  Override wins on conflicts."""
    merged = dict(base)
    for key, value in override.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(value, dict)
        ):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
