"""Path utilities for Claude Code project slug computation."""
from __future__ import annotations
from pathlib import Path


def cwd_slug(cwd: str | Path | None = None) -> str:
    """Convert a CWD path to Claude Code's project slug format.

    Example: "/home/user/projects/agent-ops" -> "-home-user-projects-agent-ops"

    IMPORTANT: Do NOT lstrip("/") -- the leading dash is part of the convention.
    """
    resolved = str(Path(cwd).resolve()) if cwd else str(Path.cwd().resolve())
    return resolved.replace("/", "-")


def get_audit_dir(cwd: str | Path | None = None) -> Path:
    """Return ~/.claude/projects/{slug}/memory/audit/ for the given cwd."""
    slug = cwd_slug(cwd)
    audit_dir = Path.home() / ".claude" / "projects" / slug / "memory" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    return audit_dir
