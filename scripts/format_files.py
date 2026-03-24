# /// script
# dependencies = ["pydantic>=2", "typer>=0.15"]
# ///
"""Auto-format and protect files: PostToolUse formatter + PreToolUse guard.

Usage:
  Post-edit:  uv run format_files.py post   (reads PostToolUse JSON from stdin)
  Pre-edit:   uv run format_files.py pre    (reads PreToolUse JSON from stdin)
  List rules: uv run format_files.py rules  (print the active rule table)

Adding a formatter or block rule:
  1. Add a Rule(...) entry to RULES below
  2. That's it -- no hook registration changes needed
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

import typer
from pydantic import BaseModel

app = typer.Typer(
    help="Auto-format edited files and block edits to protected files.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Rules table -- edit this to add formatters or blocked patterns
# ---------------------------------------------------------------------------


@dataclass
class Rule:
    """A single format or block rule.

    patterns:  fnmatch globs matched against the filename (or full path if
               the pattern contains '/').
    action:    "format" to run a command after edit, "block" to reject pre-edit.
    command:   For format rules -- command list with {file} placeholder.
    message:   For block rules -- error shown to the agent.
    """

    patterns: list[str]
    action: str  # "format" | "block"
    command: list[str] = field(default_factory=list)
    message: str = ""


RULES: list[Rule] = [
    # -- Formatters (PostToolUse) ------------------------------------------
    Rule(
        patterns=["*.tf"],
        action="format",
        command=["terraform", "fmt", "{file}"],
    ),
    # -- Blocked files (PreToolUse) ----------------------------------------
    Rule(
        patterns=[
            "pnpm-lock.yaml",
            "package-lock.json",
            "yarn.lock",
            "uv.lock",
            "composer.lock",
            "Cargo.lock",
            "poetry.lock",
            "Gemfile.lock",
        ],
        action="block",
        message="Do not edit lock files directly. Run the package manager instead.",
    ),
]


# ---------------------------------------------------------------------------
# Pydantic models for hook JSON payload
# ---------------------------------------------------------------------------


class ToolInput(BaseModel):
    file_path: str = ""


class HookPayload(BaseModel):
    tool_name: str = ""
    tool_input: ToolInput = ToolInput()


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------


def matches(file_path: str, pattern: str) -> bool:
    """Match a pattern against a file path.

    If the pattern contains '/', match against the full path.
    Otherwise, match against just the basename.
    """
    if "/" in pattern:
        return fnmatch(file_path, pattern)
    return fnmatch(Path(file_path).name, pattern)


def find_rules(file_path: str, action: str) -> list[Rule]:
    """Return all rules matching a file path and action type."""
    return [
        rule
        for rule in RULES
        if rule.action == action
        and any(matches(file_path, pat) for pat in rule.patterns)
    ]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def post() -> None:
    """PostToolUse hook: run formatters on the edited file."""
    try:
        payload = HookPayload.model_validate_json(sys.stdin.read())
    except Exception:
        raise typer.Exit(0)

    file_path = payload.tool_input.file_path
    if not file_path or not Path(file_path).is_file():
        raise typer.Exit(0)

    for rule in find_rules(file_path, "format"):
        binary = rule.command[0]
        if not shutil.which(binary):
            continue

        cmd = [arg.replace("{file}", file_path) for arg in rule.command]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            typer.echo(f"[format-files] {binary}: formatted {Path(file_path).name}", err=True)
        else:
            typer.echo(
                f"[format-files] {binary} failed on {Path(file_path).name}: {result.stderr.strip()}",
                err=True,
            )

    raise typer.Exit(0)


@app.command()
def pre() -> None:
    """PreToolUse hook: block edits to protected files."""
    try:
        payload = HookPayload.model_validate_json(sys.stdin.read())
    except Exception:
        raise typer.Exit(0)

    file_path = payload.tool_input.file_path
    if not file_path:
        raise typer.Exit(0)

    blocked = find_rules(file_path, "block")
    if blocked:
        typer.echo(f"BLOCKED: {blocked[0].message}", err=True)
        raise typer.Exit(2)

    raise typer.Exit(0)


@app.command()
def rules() -> None:
    """Print the active rule table."""
    for rule in RULES:
        icon = "F" if rule.action == "format" else "B"
        patterns = ", ".join(rule.patterns)
        detail = " ".join(rule.command) if rule.command else rule.message
        typer.echo(f"  [{icon}] {patterns}  ->  {detail}")


if __name__ == "__main__":
    app()
