# /// script
# dependencies = ["pydantic>=2", "typer>=0.15"]
# ///
"""Guard against committing a new scripts/*.py without a matching test file.

Enforces testing standard S1 (see TESTING.md): every newly-added top-level
`scripts/*.py` must ship with its `tests/test_<name>.py` in the same commit.

Scope: this enforces an agent-ops-specific convention, so it is wired only in
this repo's `.claude/settings.json` -- NOT in the plugin's `hooks/hooks.json`.
That keeps it from firing in the other repos the agency plugin is installed in.

Usage:
  Human:  uv run test-coverage-guard.py check
  Hook:   uv run test-coverage-guard.py hook  (reads JSON from stdin)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Callable

import typer
from pydantic import BaseModel

app = typer.Typer(
    help="Block committing a new scripts/*.py without a matching tests/test_*.py.",
    no_args_is_help=True,
)


# -- Pydantic models for hook JSON payload --


class ToolInput(BaseModel):
    command: str = ""


class HookPayload(BaseModel):
    tool_name: str = ""
    tool_input: ToolInput = ToolInput()


# -- Pure helpers --


EXEMPT: set[str] = set()  # add a basename here (with a one-line reason) to opt out


def expected_test_path(script_path: str) -> str:
    """Map scripts/foo-bar.py -> tests/test_foo_bar.py."""
    name = Path(script_path).stem.replace("-", "_")
    return f"tests/test_{name}.py"


def is_in_scope(path: str) -> bool:
    """True for a top-level scripts/*.py that S1 covers (not _shared/, not dunder)."""
    p = Path(path)
    return (
        len(p.parts) == 2
        and p.parts[0] == "scripts"
        and p.suffix == ".py"
        and not p.name.startswith("__")
        and p.name not in EXEMPT
    )


def evaluate(
    added_scripts: list[str], present: Callable[[str], bool]
) -> tuple[bool, str]:
    """Check newly-added scripts have tests. `present(test_path)` -> bool is injected."""
    missing = [
        (s, expected_test_path(s))
        for s in added_scripts
        if is_in_scope(s) and not present(expected_test_path(s))
    ]
    if not missing:
        return True, "All newly-added scripts have matching tests."

    lines = "\n".join(f"  {s}  ->  needs  {t}" for s, t in missing)
    return (
        False,
        "BLOCKED: new scripts added without matching tests (standard S1).\n\n"
        f"{lines}\n\n"
        "Add the test file(s) and stage them, or add the basename to EXEMPT in\n"
        "scripts/test-coverage-guard.py with a one-line reason. See TESTING.md.",
    )


# -- Git collaborators (impure) --


def staged_added_scripts() -> list[str]:
    """Paths added (status A) in the staged tree. Renames/modifies are skipped."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status", "-M"],
        capture_output=True,
        text=True,
    )
    added: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and parts[0] == "A":
            added.append(parts[1])
    return added


def _staged_paths() -> set[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return set(result.stdout.splitlines())


def default_present(test_path: str) -> bool:
    """True if the test file is tracked OR staged in this commit."""
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", test_path],
        capture_output=True,
        text=True,
    )
    if tracked.returncode == 0:
        return True
    return test_path in _staged_paths()


# -- Commands --


@app.command()
def check() -> None:
    """Check the current staged tree for new scripts missing tests."""
    allowed, message = evaluate(staged_added_scripts(), default_present)
    typer.echo(message)
    raise typer.Exit(0 if allowed else 1)


@app.command()
def hook() -> None:
    """Claude Code PreToolUse hook entry point. Reads JSON from stdin."""
    payload = HookPayload.model_validate_json(sys.stdin.read())

    if not re.search(r"git\s+commit", payload.tool_input.command):
        raise typer.Exit(0)

    allowed, message = evaluate(staged_added_scripts(), default_present)
    if not allowed:
        typer.echo(message, err=True)
        raise typer.Exit(2)

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
