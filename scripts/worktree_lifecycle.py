# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Worktree lifecycle hooks for Claude Code WorktreeCreate / WorktreeRemove.

WorktreeCreate REPLACES default git worktree creation. The hook calls
``git worktree add`` itself and prints the absolute path to stdout.

Usage:
  Create:  echo '{"worktree_name":"feat","branch":"feat-x"}' | uv run worktree_lifecycle.py create
  Remove:  echo '{"worktree_path":"/tmp/wt"}' | uv run worktree_lifecycle.py remove
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _shared.audit import write_audit_entry  # noqa: E402
from _shared.git_ops import get_repo_root  # noqa: E402
from _shared.paths import get_audit_dir  # noqa: E402
from frontmatter_config import resolve_typed  # noqa: E402

import typer
from pydantic import BaseModel

app = typer.Typer(
    help="Worktree lifecycle hooks for Claude Code.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Config model (namespace: "worktree" in CLAUDE.md frontmatter)
# ---------------------------------------------------------------------------


class WorktreeConfig(BaseModel):
    propagate_hooks: bool = True
    check_uncommitted: bool = True
    clean_branches: bool = False


# ---------------------------------------------------------------------------
# Stdin payload models
# ---------------------------------------------------------------------------


class CreatePayload(BaseModel):
    worktree_name: str
    # Optional: a branchless payload creates the worktree from HEAD (git
    # names the new branch after the worktree directory). The create command
    # already guards `if payload.branch:` -- requiring it here just crashed
    # worktree creation on branchless payloads.
    branch: str = ""


class RemovePayload(BaseModel):
    worktree_path: str


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

SKIP_ENV = {".env.example", ".envrc"}


def copy_git_hooks(*, main_repo: Path, worktree: Path) -> list[str]:
    """Copy executable hooks from main repo into worktree's git dir.

    Worktree .git is a FILE pointing to the real git dir. We resolve the
    real git dir via ``git rev-parse --git-dir`` run inside the worktree,
    then copy executable hooks from the main repo's ``.git/hooks/`` into
    the worktree's resolved git dir ``hooks/`` subdirectory.

    Returns list of copied hook names.
    """
    main_hooks_dir = main_repo / ".git" / "hooks"
    if not main_hooks_dir.is_dir():
        return []

    # Resolve the worktree's real git directory
    result = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        capture_output=True,
        text=True,
        cwd=str(worktree),
    )
    if result.returncode != 0:
        return []

    wt_git_dir = Path(result.stdout.strip())
    if not wt_git_dir.is_absolute():
        wt_git_dir = (worktree / wt_git_dir).resolve()

    wt_hooks_dir = wt_git_dir / "hooks"
    wt_hooks_dir.mkdir(parents=True, exist_ok=True)

    copied: list[str] = []
    for hook_file in main_hooks_dir.iterdir():
        if not hook_file.is_file():
            continue
        if not os.access(hook_file, os.X_OK):
            continue
        dest = wt_hooks_dir / hook_file.name
        shutil.copy2(hook_file, dest)
        # Ensure executable bit is preserved
        dest.chmod(dest.stat().st_mode | 0o755)
        copied.append(hook_file.name)

    return copied


def check_env_files(worktree: Path) -> list[str]:
    """Check for .env files in the worktree root.

    Skips ``.env.example`` and ``.envrc``. Returns a list of warning strings.
    """
    warnings: list[str] = []
    for entry in sorted(worktree.iterdir()):
        name = entry.name
        if name in SKIP_ENV:
            continue
        if name.startswith(".env") and entry.is_file():
            warnings.append(
                f"WARNING: Found {name} in worktree. "
                f"Ensure it is not committed."
            )
    return warnings


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


def _write_audit(event: dict) -> None:
    """Append a JSON event to the worktree audit log."""
    audit_dir = get_audit_dir()
    write_audit_entry(audit_dir, "worktree-events", event)


# ---------------------------------------------------------------------------
# Typer commands
# ---------------------------------------------------------------------------


@app.command()
def create() -> None:
    """WorktreeCreate hook. Reads JSON from stdin, creates worktree, copies hooks.

    Prints the absolute worktree path to stdout on success.
    Exit 0 = success, non-zero = failure.
    """
    payload = CreatePayload.model_validate_json(sys.stdin.read())
    config = resolve_typed(WorktreeConfig, "worktree")

    # Determine worktree path: sibling .worktrees/ directory at the REPO
    # ROOT. Sessions started in a subdirectory must not grow a nested
    # .worktrees/ there (and hook propagation would silently no-op against
    # a non-root "main repo" path).
    repo_root = get_repo_root(Path.cwd())
    wt_base = repo_root / ".worktrees"
    wt_base.mkdir(parents=True, exist_ok=True)
    wt_path = wt_base / payload.worktree_name

    # Run git worktree add
    cmd = ["git", "worktree", "add", str(wt_path)]
    if payload.branch:
        cmd.extend(["-b", payload.branch])

    result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(repo_root))
    if result.returncode != 0:
        typer.echo(f"Failed to create worktree: {result.stderr.strip()}", err=True)
        raise typer.Exit(1)

    # Copy git hooks from main repo
    copied: list[str] = []
    if config.propagate_hooks:
        copied = copy_git_hooks(main_repo=repo_root, worktree=wt_path)
        if copied:
            typer.echo(
                f"Propagated {len(copied)} hook(s): {', '.join(copied)}", err=True
            )

    # Check for .env files
    env_warnings = check_env_files(wt_path)
    for warning in env_warnings:
        typer.echo(warning, err=True)

    # Audit
    _write_audit(
        {
            "event": "worktree_created",
            "worktree_name": payload.worktree_name,
            "branch": payload.branch,
            "path": str(wt_path),
            "hooks_copied": copied,
            "env_warnings": len(env_warnings),
        }
    )

    # Print absolute path to stdout (critical -- Claude Code reads this)
    print(str(wt_path.resolve()))
    raise typer.Exit(0)


@app.command()
def remove() -> None:
    """WorktreeRemove hook. Reads JSON from stdin, checks uncommitted work, logs audit.

    Exit 0 always (debug-only visibility).
    """
    payload = RemovePayload.model_validate_json(sys.stdin.read())
    config = resolve_typed(WorktreeConfig, "worktree")
    wt_path = Path(payload.worktree_path)

    uncommitted = False
    uncommitted_details = ""

    # Check for uncommitted work
    if config.check_uncommitted and wt_path.is_dir():
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=str(wt_path),
        )
        if result.stdout.strip():
            uncommitted = True
            uncommitted_details = result.stdout.strip()
            typer.echo(
                f"WARNING: Worktree {wt_path} has uncommitted changes:\n"
                f"{uncommitted_details}",
                err=True,
            )

    # Audit
    _write_audit(
        {
            "event": "worktree_removed",
            "path": str(wt_path),
            "had_uncommitted": uncommitted,
            "uncommitted_details": uncommitted_details if uncommitted else None,
        }
    )

    # Always exit 0 -- removal is debug-only visibility
    raise typer.Exit(0)


if __name__ == "__main__":
    app()
