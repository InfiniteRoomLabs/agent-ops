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
from datetime import date
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).parent))
from _shared.git_ops import get_current_branch  # noqa: E402

import typer
from pydantic import BaseModel

app = typer.Typer(
    help="Guard against commits on protected branches without a CHANGELOG.md update.",
    no_args_is_help=True,
)

PROTECTED_BRANCHES = re.compile(r"^(main|master|release/.+)$")

TEMPLATE_PATH = Path(__file__).parent / "templates" / "CHANGELOG.template.md"


# -- Pydantic models for hook JSON payload --


class ToolInput(BaseModel):
    command: str = ""


class HookPayload(BaseModel):
    tool_name: str = ""
    tool_input: ToolInput = ToolInput()


# -- Shared logic --


def changelog_is_staged() -> bool:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return "CHANGELOG.md" in result.stdout.splitlines()


def repo_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return Path.cwd()
    return Path(result.stdout.strip())


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

    if changelog_is_staged():
        return True, f"CHANGELOG.md is staged. Good to go on '{branch}'."

    root = root or repo_root()
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

    # Reject combined add+commit in a single command -- staging must be
    # a separate step so the hook can inspect what's actually staged.
    if re.search(r"git\s+add\b", payload.tool_input.command):
        typer.echo(
            "BLOCKED: Run 'git add' and 'git commit' as separate Bash calls.\n"
            "The changelog guard needs to inspect staged files between the two steps.\n"
            "Stage your files first, then commit in a follow-up command.",
            err=True,
        )
        raise typer.Exit(2)

    branch = get_current_branch()
    allowed, message = evaluate(branch)

    if not allowed:
        typer.echo(message, err=True)
        raise typer.Exit(2)

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
