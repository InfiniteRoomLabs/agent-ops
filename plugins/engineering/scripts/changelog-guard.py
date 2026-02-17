# /// script
# dependencies = ["pydantic>=2", "typer>=0.15"]
# ///
"""Guard against commits on protected branches without a CHANGELOG.md update.

Usage:
  Human:  uv run changelog-guard.py check
  Hook:   uv run changelog-guard.py hook  (reads JSON from stdin)
"""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Annotated, Optional

import typer
from pydantic import BaseModel

app = typer.Typer(
    help="Guard against commits on protected branches without a CHANGELOG.md update.",
    no_args_is_help=True,
)

PROTECTED_BRANCHES = re.compile(r"^(main|master|release/.+)$")


# -- Pydantic models for hook JSON payload --


class ToolInput(BaseModel):
    command: str = ""


class HookPayload(BaseModel):
    tool_name: str = ""
    tool_input: ToolInput = ToolInput()


# -- Shared logic --


def get_current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def changelog_is_staged() -> bool:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return "CHANGELOG.md" in result.stdout.splitlines()


def evaluate(branch: str) -> tuple[bool, str]:
    """Check if a commit is allowed. Returns (allowed, message)."""
    if not PROTECTED_BRANCHES.match(branch):
        return True, f"Branch '{branch}' is not protected. No CHANGELOG requirement."

    if changelog_is_staged():
        return True, f"CHANGELOG.md is staged. Good to go on '{branch}'."

    return (
        False,
        f"BLOCKED: Committing to '{branch}' without updating CHANGELOG.md.\n\n"
        "Update CHANGELOG.md and stage it before committing on release or main branches.\n"
        "If this is intentional, unstage and recommit from a feature branch.",
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


@app.command()
def hook() -> None:
    """Claude Code PreToolUse hook entry point. Reads JSON from stdin."""
    payload = HookPayload.model_validate_json(sys.stdin.read())

    if not re.search(r"git\s+commit", payload.tool_input.command):
        raise typer.Exit(0)

    branch = get_current_branch()
    allowed, message = evaluate(branch)

    if not allowed:
        typer.echo(message)
        raise typer.Exit(2)

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
