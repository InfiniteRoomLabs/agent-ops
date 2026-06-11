"""Path utilities for Claude Code project slug computation."""
from __future__ import annotations

import os
import re
from pathlib import Path

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def project_dir(fallback: str | Path | None = None) -> Path:
    """The session's project root, for slug/state keying.

    Prefers ``CLAUDE_PROJECT_DIR`` (set by Claude Code for hooks) over the
    given fallback, over the live process cwd: hooks and subshells can run
    from subdirectories or worktrees, which would otherwise scatter state
    across multiple slugs.
    """
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env)
    return Path(fallback) if fallback else Path.cwd()


def cwd_slug(cwd: str | Path | None = None) -> str:
    """Convert a CWD path to Claude Code's project slug format.

    Claude Code replaces every non-alphanumeric character (not just "/")
    with "-", preserving case. Verified empirically 2026-06-11: a session
    in /tmp/slug.test_x writes its transcript under
    ~/.claude/projects/-tmp-slug-test-x.

    Example: "/home/user/.config/fish" -> "-home-user--config-fish"

    With no argument, keys off :func:`project_dir` (CLAUDE_PROJECT_DIR,
    then process cwd) so all hook scripts resolve the same slug.

    IMPORTANT: Do NOT lstrip("/") -- the leading dash is part of the convention.
    """
    resolved = str(Path(cwd).resolve()) if cwd else str(project_dir().resolve())
    return _NON_ALNUM.sub("-", resolved)


def get_audit_dir(cwd: str | Path | None = None) -> Path:
    """Return ~/.claude/projects/{slug}/memory/audit/ for the given cwd."""
    slug = cwd_slug(cwd)
    audit_dir = Path.home() / ".claude" / "projects" / slug / "memory" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir
