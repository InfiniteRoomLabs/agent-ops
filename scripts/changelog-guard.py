# /// script
# dependencies = ["pydantic>=2", "typer>=0.15"]
# ///
"""Guard against commits on protected branches without a CHANGELOG.md update.

Usage:
  Human:  uv run changelog-guard.py check
  Human:  uv run changelog-guard.py push-check --command "git push origin main"
  Hook:   uv run changelog-guard.py hook  (reads JSON from stdin)

The hook guards two events on protected branches (main/master/release/*):
  * git commit -- requires CHANGELOG.md be staged in the commit.
  * git push   -- requires CHANGELOG.md exist as a tracked file in the repo.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).parent))
from _shared.git_ops import (  # noqa: E402
    PROTECTED_BRANCHES_DEFAULT,
    STAGING_SEPARATION_MESSAGE,
    get_current_branch,
    get_repo_root,
    get_staged_files,
    resolve_repo_root,
    runs_git_command,
    stages_at_commit_time,
)
from _shared.hook_payload import BashHookPayload  # noqa: E402

import typer

app = typer.Typer(
    help="Guard against commits on protected branches without a CHANGELOG.md update.",
    no_args_is_help=True,
)

PROTECTED_BRANCHES = re.compile(PROTECTED_BRANCHES_DEFAULT)

TEMPLATE_PATH = Path(__file__).parent / "templates" / "CHANGELOG.template.md"


# -- Shared logic --


def changelog_is_staged(root: Path | None = None) -> bool:
    return "CHANGELOG.md" in get_staged_files(root)


def render_template(today: str | None = None) -> str:
    """Read template file and substitute {{VAR}} placeholders."""
    today = today or date.today().isoformat()
    text = TEMPLATE_PATH.read_text(encoding="utf-8")
    return text.replace("{{DATE}}", today)


def generate_changelog(target: Path, today: str | None = None) -> Path:
    """Write the example CHANGELOG.md to `target`. Returns the path written."""
    target.write_text(render_template(today), encoding="utf-8")
    return target


def evaluate(branch: str, root: Path | None = None) -> tuple[bool, str]:
    """Check if a commit is allowed. Returns (allowed, message).

    Side effect: when CHANGELOG.md does not exist on a protected branch, an
    example template is generated at the repo root before the blocking
    message is returned, so the agent has a starting point to edit.
    """
    if not PROTECTED_BRANCHES.match(branch):
        return True, f"Branch '{branch}' is not protected. No CHANGELOG requirement."

    root = root or get_repo_root()

    if changelog_is_staged(root):
        return True, f"CHANGELOG.md is staged. Good to go on '{branch}'."

    changelog = root / "CHANGELOG.md"

    if not changelog.exists():
        generate_changelog(changelog)
        return (
            False,
            f"BLOCKED: Committing to '{branch}' without a CHANGELOG.md.\n\n"
            f"No CHANGELOG.md existed, so an EXAMPLE template was generated at:\n"
            f"  {changelog}\n\n"
            "What to do now:\n"
            "  1. Open CHANGELOG.md.\n"
            "  2. Keep the first five lines exactly as written -- they are the\n"
            "     canonical header (title + the two paragraphs about Keep a\n"
            "     Changelog and Semantic Versioning).\n"
            "  3. Delete EVERYTHING from the `<!-- EXAMPLE BLOCK -->` HTML\n"
            "     comment to the end of the file. The example releases\n"
            "     (`widget` CLI, `0.1.0`, `0.1.1`) are placeholders -- they\n"
            "     are NOT your project and must not be committed as-is.\n"
            "  4. Replace the deleted block with real release entries that\n"
            "     describe the changes in this commit, using the section\n"
            "     names shown in the example (Added/Changed/Deprecated/\n"
            "     Removed/Fixed/Security). Newest release on top.\n"
            "  5. `git add CHANGELOG.md` and re-run the commit.",
        )

    return (
        False,
        f"BLOCKED: Committing to '{branch}' without updating CHANGELOG.md.\n\n"
        "Update CHANGELOG.md and stage it before committing on release or main branches.\n"
        "If this is intentional, unstage and recommit from a feature branch.",
    )


# -- Push-time logic --


def changelog_tracked(root: Path | None = None) -> bool:
    """True if CHANGELOG.md is tracked by git (committed, not just on disk)."""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", "CHANGELOG.md"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    return result.returncode == 0


def local_branches(root: Path | None = None) -> set[str]:
    """Return the set of local branch names."""
    result = subprocess.run(
        ["git", "branch", "--format=%(refname:short)"],
        capture_output=True,
        text=True,
        cwd=root,
    )
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}


def resolve_push_targets(
    command: str, current_branch: str, root: Path | None = None
) -> list[str] | None:
    """Resolve the branch ref(s) a `git push` command targets.

    Returns a list of target branch names, or None to signal the push needs no
    CHANGELOG check (a deletion or a tags-only push).
    """
    # Tokens after the `push` subcommand.
    tokens = command.split()
    try:
        push_idx = tokens.index("push")
    except ValueError:
        # Match the loose `git\s+push` the hook used; fall back to current branch.
        return [current_branch]
    args = tokens[push_idx + 1 :]

    has_tags = False
    expand_all = False
    positionals: list[str] = []
    for tok in args:
        if tok.startswith("-"):
            if tok in ("--delete", "-d"):
                return None  # deletion -- no changelog requirement
            if tok == "--tags":
                has_tags = True
            elif tok in ("--all", "--mirror"):
                expand_all = True
            # Other flags are boolean for our purposes; ignore.
            continue
        positionals.append(tok)

    if expand_all:
        # Pushing all branches -- require a changelog if a protected branch exists.
        return sorted(local_branches(root))

    # First positional is the remote; the rest are refspecs.
    refspecs = positionals[1:] if positionals else []

    if not refspecs:
        if has_tags:
            return None  # `git push --tags` (no branch refspec) -- tags only
        return [current_branch]

    targets: list[str] = []
    for spec in refspecs:
        if ":" in spec:
            src, _, dst = spec.partition(":")
            if src == "":
                continue  # `:dst` is a delete of dst -- skip
            target = dst
        else:
            target = spec
        if target in ("HEAD", ""):
            target = current_branch
        targets.append(target)

    if not targets:
        return None  # only deletions were specified
    return targets


def evaluate_push(
    command: str, current_branch: str, root: Path | None = None
) -> tuple[bool, str]:
    """Check if a `git push` is allowed. Returns (allowed, message).

    Blocks when the push targets a protected branch and no CHANGELOG.md is
    tracked in the repo. When CHANGELOG.md is missing from disk entirely, an
    example template is generated so the agent has a starting point.
    """
    root = root or get_repo_root()
    targets = resolve_push_targets(command, current_branch, root)

    if targets is None:
        return True, "Push is a delete/tags-only operation. No CHANGELOG requirement."

    protected = [t for t in targets if PROTECTED_BRANCHES.match(t)]
    if not protected:
        return True, "Push targets no protected branch. No CHANGELOG requirement."

    if changelog_tracked(root):
        return True, f"CHANGELOG.md is tracked. Good to push to {protected}."

    changelog = root / "CHANGELOG.md"
    if not changelog.exists():
        generate_changelog(changelog)
        hint = (
            f"No CHANGELOG.md existed, so an EXAMPLE template was generated at:\n"
            f"  {changelog}\n"
            "Edit it (keep the first five header lines, delete the example block),\n"
            "then commit it:\n"
        )
    else:
        hint = "CHANGELOG.md exists on disk but is not committed. Commit it:\n"

    return (
        False,
        f"BLOCKED: Pushing to protected branch {protected} but no CHANGELOG.md is\n"
        f"tracked in the repo.\n\n"
        f"{hint}"
        "  1. git add CHANGELOG.md\n"
        '  2. git commit -m "docs: add changelog"\n'
        "  3. re-run your push\n\n"
        "A generated-but-uncommitted file does NOT unblock the push -- it must be\n"
        "tracked. If this is intentional, push to a feature branch instead.",
    )


# -- Commands --


@app.command()
def check(
    branch: Annotated[
        Optional[str],
        typer.Option("--branch", "-b", help="Branch to check. Defaults to current branch."),
    ] = None,
) -> None:
    """Check if the current branch requires a CHANGELOG update before committing."""
    branch = branch or get_current_branch()

    if not branch:
        typer.echo("Could not determine current branch.", err=True)
        raise typer.Exit(1)

    allowed, message = evaluate(branch)
    typer.echo(message)
    raise typer.Exit(0 if allowed else 1)


@app.command("push-check")
def push_check(
    command: Annotated[
        str,
        typer.Option("--command", "-c", help="The git push command to evaluate."),
    ],
) -> None:
    """Check if a `git push` command is allowed on the current branch."""
    branch = get_current_branch()
    allowed, message = evaluate_push(command, branch)
    typer.echo(message)
    raise typer.Exit(0 if allowed else 1)


@app.command()
def hook() -> None:
    """Claude Code PreToolUse hook entry point. Reads JSON from stdin."""
    payload = BashHookPayload.model_validate_json(sys.stdin.read())
    command = payload.tool_input.command

    # Push guard: require a tracked CHANGELOG before pushing to a protected branch.
    if runs_git_command(command, "push"):
        root = resolve_repo_root(command, payload.cwd)
        branch = get_current_branch(root)
        allowed, message = evaluate_push(command, branch, root)
        if not allowed:
            typer.echo(message, err=True)
            raise typer.Exit(2)
        raise typer.Exit(0)

    if not runs_git_command(command, "commit"):
        raise typer.Exit(0)

    root = resolve_repo_root(command, payload.cwd)
    branch = get_current_branch(root)
    if not PROTECTED_BRANCHES.match(branch):
        raise typer.Exit(0)  # no CHANGELOG requirement -> no staging rules either

    # Reject commands where the staged index the hook inspects is not the
    # index the commit will record. Staging must be a separate step.
    if stages_at_commit_time(command):
        typer.echo(STAGING_SEPARATION_MESSAGE.format(guard="changelog"), err=True)
        raise typer.Exit(2)

    allowed, message = evaluate(branch, root)

    if not allowed:
        typer.echo(message, err=True)
        raise typer.Exit(2)

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
