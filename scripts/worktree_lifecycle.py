# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Worktree lifecycle hooks for Claude Code WorktreeCreate / WorktreeRemove.

WorktreeCreate REPLACES default git worktree creation. The hook calls
``git worktree add`` itself and prints the absolute path to stdout.

Claude Code sends the common hook fields (``session_id``, ``transcript_path``,
``cwd``, ...) plus ``hook_event_name`` and, for WorktreeCreate, ``name`` (a
subagent launched with worktree isolation sends ``agent-<id>``); for
WorktreeRemove, ``worktree_path``.

Usage:
  Create:  echo '{"name":"feat","branch":"feat-x"}' | uv run worktree_lifecycle.py create
  Remove:  echo '{"worktree_path":"/tmp/wt"}' | uv run worktree_lifecycle.py remove
  SubagentStop:  echo '{"agent_id":"abc123"}' | uv run worktree_lifecycle.py subagent-stop
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import TypeVar

sys.path.insert(0, str(Path(__file__).parent))
from _shared.audit import write_audit_entry  # noqa: E402
from _shared.git_ops import get_repo_root  # noqa: E402
from _shared.paths import get_audit_dir  # noqa: E402
from _shared.frontmatter_config import resolve_typed  # noqa: E402

import typer
from pydantic import BaseModel, ValidationError

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


# ---------------------------------------------------------------------------
# Stdin payload models
# ---------------------------------------------------------------------------


class CreatePayload(BaseModel):
    # The worktree name. Claude Code sends it as `name`; the earlier
    # `worktree_name` field never existed in the hook input.
    name: str
    # Not sent by Claude Code; accepted for manual runs. A branchless payload
    # creates the worktree from HEAD (git names the new branch after the
    # worktree directory).
    branch: str = ""


class RemovePayload(BaseModel):
    worktree_path: str


_Payload = TypeVar("_Payload", bound=BaseModel)


def parse_payload(
    raw: str, model: type[_Payload], required: str
) -> tuple[_Payload | None, str]:
    """Parse hook stdin JSON into ``model``, requiring a non-empty ``required`` field.

    Returns ``(payload, "")``, or ``(None, reason)`` when stdin is not a JSON
    object, lacks ``required``, or does not fit ``model``. The reason lists the
    keys that did arrive, so a future change to the hook input can be
    diagnosed from the hook's error message alone.
    """
    try:
        data = json.loads(raw)
    except ValueError as exc:
        return None, f"stdin is not valid JSON ({exc})"
    if not isinstance(data, dict):
        return None, f"stdin is a JSON {type(data).__name__}, not an object"
    if not data.get(required):
        keys = ", ".join(sorted(data)) or "none"
        return None, f"payload has no `{required}` field (received keys: {keys})"
    try:
        return model.model_validate(data), ""
    except ValidationError as exc:
        problems = "; ".join(
            f"`{'.'.join(map(str, err['loc']))}`: {err['msg']}" for err in exc.errors()
        )
        return None, f"payload does not match the expected shape ({problems})"


class SubagentStopPayload(BaseModel):
    agent_id: str


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
        # Git never runs `*.sample` hooks. They must be skipped by name: git's
        # templates install them executable, and on Windows os.access(X_OK)
        # is true for every file.
        if hook_file.suffix == ".sample":
            continue
        if not os.access(hook_file, os.X_OK):
            continue
        dest = wt_hooks_dir / hook_file.name
        shutil.copy2(hook_file, dest)
        # Ensure executable bit is preserved
        dest.chmod(dest.stat().st_mode | 0o755)
        copied.append(hook_file.name)

    return copied


def check_worktree_env_files(worktree: Path) -> list[str]:
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
# Safe removal
# ---------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], capture_output=True, text=True, cwd=str(cwd))


def _main_repo_root(cwd: Path) -> Path:
    """Root of the main checkout, even when ``cwd`` is inside a linked worktree."""
    r = _git(cwd, "rev-parse", "--path-format=absolute", "--git-common-dir")
    common = r.stdout.strip()
    if r.returncode != 0 or not common:
        return get_repo_root(cwd)
    return Path(common).parent


def _remove_worktree_if_safe(repo_root: Path, wt_path: Path) -> tuple[bool, str]:
    """Remove a hook-created worktree (and its same-named branch) only if no work is lost.

    Safe = registered worktree of this repo directly under ``<repo_root>/.worktrees/``,
    clean ``git status`` (untracked files count), and no commit reachable from HEAD
    that is missing from every other local branch and remote-tracking ref.
    """
    wt = wt_path.resolve()
    if wt.parent != (repo_root / ".worktrees").resolve():
        return False, "not directly under .worktrees/"
    listed = _git(repo_root, "worktree", "list", "--porcelain").stdout.splitlines()
    registered = {Path(line[9:]).resolve() for line in listed if line.startswith("worktree ")}
    if wt not in registered:
        return False, "not a registered worktree of this repo"

    status = _git(wt, "status", "--porcelain")
    if status.returncode != 0 or status.stdout.strip():
        return False, "uncommitted or untracked changes"

    branch = _git(wt, "symbolic-ref", "--short", "-q", "HEAD").stdout.strip()
    # Commits reachable from HEAD but from no other local branch or remote-tracking
    # ref. `--exclude=<own branch>` (matched relative to refs/heads/) hides this
    # worktree's own branch from the following --branches glob; an empty result
    # means deleting the branch loses nothing.
    cmd = ["rev-list", "-n1", "HEAD", "--not"]
    if branch:
        cmd.append(f"--exclude={branch}")
    cmd += ["--branches", "--remotes"]
    unique = _git(wt, *cmd)
    if unique.returncode != 0 or unique.stdout.strip():
        return False, "HEAD has commits not on any other branch"

    rm = _git(repo_root, "worktree", "remove", str(wt))
    if rm.returncode != 0:
        return False, f"git worktree remove failed: {rm.stderr.strip()}"
    if branch and branch == wt.name:
        _git(repo_root, "branch", "-d", branch)  # refuses if unmerged; leave it then
    return True, "removed"


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
    payload, reason = parse_payload(sys.stdin.read(), CreatePayload, "name")
    if payload is None:
        typer.echo(f"WorktreeCreate hook: {reason}; no worktree created.", err=True)
        raise typer.Exit(1)
    config = resolve_typed(WorktreeConfig, "worktree")

    # Determine worktree path: sibling .worktrees/ directory at the REPO
    # ROOT. Sessions started in a subdirectory must not grow a nested
    # .worktrees/ there (and hook propagation would silently no-op against
    # a non-root "main repo" path).
    repo_root = get_repo_root(Path.cwd())
    wt_base = repo_root / ".worktrees"
    wt_base.mkdir(parents=True, exist_ok=True)
    wt_path = wt_base / payload.name

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
    env_warnings = check_worktree_env_files(wt_path)
    for warning in env_warnings:
        typer.echo(warning, err=True)

    # Audit
    _write_audit(
        {
            "event": "worktree_created",
            "worktree_name": payload.name,
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
    """WorktreeRemove hook. Reads JSON from stdin, deletes the worktree if safe, logs audit.

    Claude Code treats exit 0 as "removed" and never deletes a hook-created
    worktree itself, so this deletes it. Exit 1 when the directory is kept
    (unsaved work), which makes Claude Code keep the worktree too.
    """
    payload, reason = parse_payload(sys.stdin.read(), RemovePayload, "worktree_path")
    if payload is None:
        typer.echo(f"WARNING: WorktreeRemove hook: {reason}; nothing audited.", err=True)
        raise typer.Exit(0)
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

    removed, reason = _remove_worktree_if_safe(_main_repo_root(Path.cwd()), wt_path)
    if not removed and not wt_path.exists():
        removed, reason = True, "already gone"

    # Audit
    _write_audit(
        {
            "event": "worktree_removed",
            "path": str(wt_path),
            "had_uncommitted": uncommitted,
            "uncommitted_details": uncommitted_details if uncommitted else None,
            "removed": removed,
            "reason": reason,
        }
    )

    if removed:
        raise typer.Exit(0)
    typer.echo(f"Keeping worktree {wt_path}: {reason}", err=True)
    raise typer.Exit(1)


@app.command("subagent-stop")
def subagent_stop() -> None:
    """SubagentStop hook. Removes the finished subagent's clean worktree.

    Claude Code keeps hook-created subagent worktrees and skips WorktreeRemove for
    them. The worktree is named ``agent-<agent_id>`` (id used as-is if it already
    carries the prefix). Only that one is touched. Always exits 0, no stdout.
    """
    payload, _ = parse_payload(sys.stdin.read(), SubagentStopPayload, "agent_id")
    if payload is None:
        raise typer.Exit(0)
    agent_id = payload.agent_id
    name = agent_id if agent_id.startswith("agent-") else f"agent-{agent_id}"
    if "/" in name or ".." in name:
        raise typer.Exit(0)

    repo_root = _main_repo_root(Path.cwd())
    wt_path = repo_root / ".worktrees" / name
    if not wt_path.exists():
        raise typer.Exit(0)

    removed, reason = _remove_worktree_if_safe(repo_root, wt_path)
    _write_audit(
        {
            "event": "subagent_worktree_cleanup",
            "path": str(wt_path),
            "removed": removed,
            "reason": reason,
        }
    )
    raise typer.Exit(0)


if __name__ == "__main__":
    app()
