# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Guard for InstructionsLoaded hook -- validates CLAUDE.md and rules files.

Checks loaded instruction files for:
  - UTF-8 encoding artifacts (Windows-1252 smart quotes, dashes, etc.)
  - Unresolved placeholder markers ([PLACEHOLDER])

Usage:
  Human:  uv run instructions-guard.py check <file>
  Hook:   uv run instructions-guard.py hook  (reads JSON from stdin)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel

# Ensure sibling modules are importable when invoked via uv run
sys.path.insert(0, str(Path(__file__).parent))

from frontmatter_config import resolve_typed  # noqa: E402

app = typer.Typer(
    help="Validate CLAUDE.md and rules files when loaded into context.",
    no_args_is_help=True,
)

# -- Windows-1252 artifact codepoints --

ENCODING_ARTIFACTS: set[str] = {
    "\u201c",  # left double quotation mark
    "\u201d",  # right double quotation mark
    "\u2018",  # left single quotation mark
    "\u2019",  # right single quotation mark
    "\u2013",  # en dash
    "\u2014",  # em dash
    "\u2026",  # horizontal ellipsis
    "\u2022",  # bullet
    "\u00a0",  # no-break space
    "\u2192",  # rightwards arrow
}

PLACEHOLDER_RE = re.compile(r"\[PLACEHOLDER\]", re.IGNORECASE)


# -- Pydantic models --


class EnforcementConfig(BaseModel):
    encoding: bool = True
    placeholder_check: bool = True


class HookPayload(BaseModel):
    file_path: str = ""
    memory_type: str = ""
    load_reason: str = ""


# -- Core validation --


def validate_file(
    path: Path,
    *,
    encoding_check: bool = True,
    placeholder_check: bool = True,
) -> list[str]:
    """Returns list of warning strings. Empty = clean."""
    warnings: list[str] = []

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, PermissionError, UnicodeDecodeError):
        return warnings

    if encoding_check:
        found = {ch for ch in content if ch in ENCODING_ARTIFACTS}
        if found:
            chars = ", ".join(f"U+{ord(c):04X}" for c in sorted(found))
            warnings.append(
                f"Encoding: Windows-1252 artifacts detected in {path.name}: {chars}"
            )

    if placeholder_check:
        matches = PLACEHOLDER_RE.findall(content)
        if matches:
            warnings.append(
                f"Placeholder: Unresolved [PLACEHOLDER] marker(s) in {path.name} "
                f"({len(matches)} found)"
            )

    return warnings


# -- Typer commands --


@app.command()
def check(
    file_path: Annotated[
        str,
        typer.Argument(help="Path to the file to validate."),
    ],
) -> None:
    """CLI validation of a CLAUDE.md or rules file."""
    cfg = resolve_typed(EnforcementConfig, "enforcement")
    path = Path(file_path)

    warnings = validate_file(
        path,
        encoding_check=cfg.encoding,
        placeholder_check=cfg.placeholder_check,
    )

    if warnings:
        for w in warnings:
            typer.echo(w, err=True)
        raise typer.Exit(1)

    typer.echo(f"{path.name}: clean", err=True)
    raise typer.Exit(0)


@app.command()
def hook() -> None:
    """Claude Code InstructionsLoaded hook entry point. Reads JSON from stdin."""
    payload = HookPayload.model_validate_json(sys.stdin.read())

    if not payload.file_path:
        raise typer.Exit(0)

    cfg = resolve_typed(EnforcementConfig, "enforcement")
    path = Path(payload.file_path)

    warnings = validate_file(
        path,
        encoding_check=cfg.encoding,
        placeholder_check=cfg.placeholder_check,
    )

    if warnings:
        message = "Instructions Guard Warnings:\n" + "\n".join(f"  - {w}" for w in warnings)
        typer.echo(json.dumps({"systemMessage": message}))

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
