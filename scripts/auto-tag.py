# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "pyyaml>=6"]
# ///
"""Auto-tag on version bump: PostToolUse hook + CI entry point.

Usage:
  Hook:  uv run auto-tag.py hook  (reads PostToolUse JSON from stdin)
  CI:    uv run auto-tag.py ci    (reads filesystem, no stdin)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

sys.path.insert(0, str(Path(__file__).parent))
from _shared.changelog import get_latest_changelog_version, has_content_under_header  # noqa: E402
from _shared.git_ops import get_latest_tag  # noqa: E402

import typer
from pydantic import BaseModel

app = typer.Typer(
    help="Auto-tag releases when CHANGELOG version is ahead of the latest git tag.",
    no_args_is_help=True,
)


# -- Pydantic models --


class AutoTagResult(BaseModel):
    should_tag: bool = False
    version: str = ""  # bare: "1.3.0"
    tag_name: str = ""  # prefixed: "v1.3.0"
    reason: str = ""
    manifest_mismatch: bool = False


class ToolInput(BaseModel):
    command: str = ""


class HookPayload(BaseModel):
    tool_name: str = ""
    tool_input: ToolInput = ToolInput()


# -- Core decision function --


def evaluate_auto_tag(
    project_dir: Path,
    *,
    changelog_prefix: str = "agency-",
    tag_prefix: str = "v",
    manifest_path: str = ".claude-plugin/plugin.json",
) -> AutoTagResult:
    """Determine if a tag should be created.

    1. Parse CHANGELOG for latest version header
    2. Verify content under header
    3. Read manifest version
    4. Compare CHANGELOG vs manifest (sanity check)
    5. Get latest git tag
    6. Compare CHANGELOG version vs tag version
    """
    changelog_path = project_dir / "CHANGELOG.md"

    # 1. Parse CHANGELOG for latest version
    changelog_version = get_latest_changelog_version(
        changelog_path, strip_prefix=changelog_prefix
    )
    if not changelog_version:
        return AutoTagResult(reason="No version found in CHANGELOG.md")

    tag_name = f"{tag_prefix}{changelog_version}"

    # 2. Verify content under header
    if not has_content_under_header(
        changelog_path, changelog_version, prefix=changelog_prefix
    ):
        return AutoTagResult(
            version=changelog_version,
            tag_name=tag_name,
            reason=f"CHANGELOG section for {changelog_version} has no content",
        )

    # 3. Read manifest version
    manifest_file = project_dir / manifest_path
    manifest_version: str | None = None
    if manifest_file.is_file():
        try:
            data = json.loads(manifest_file.read_text())
            manifest_version = data.get("version")
        except (json.JSONDecodeError, OSError):
            pass

    # 4. Compare CHANGELOG vs manifest
    if manifest_version and manifest_version != changelog_version:
        return AutoTagResult(
            version=changelog_version,
            tag_name=tag_name,
            manifest_mismatch=True,
            reason=(
                f"CHANGELOG version {changelog_version} does not match "
                f"manifest version {manifest_version}"
            ),
        )

    # 5. Get latest git tag
    latest_tag = get_latest_tag(tag_prefix)
    if latest_tag:
        latest_tag_version = latest_tag[len(tag_prefix) :] if latest_tag.startswith(tag_prefix) else latest_tag
    else:
        latest_tag_version = None

    # 6. Compare CHANGELOG version vs tag version
    if latest_tag_version == changelog_version:
        return AutoTagResult(
            version=changelog_version,
            tag_name=tag_name,
            reason=f"Tag {tag_name} already exists",
        )

    return AutoTagResult(
        should_tag=True,
        version=changelog_version,
        tag_name=tag_name,
        reason=f"CHANGELOG {changelog_version} is ahead of tag {latest_tag or '(none)'}",
    )


# -- Tag creation helper --


def create_and_push_tag(tag_name: str, version: str) -> bool:
    """Create an annotated tag and push it. Returns True on success."""
    result = subprocess.run(
        ["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        typer.echo(f"Failed to create tag: {result.stderr}", err=True)
        return False

    result = subprocess.run(
        ["git", "push", "origin", tag_name],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        typer.echo(f"Failed to push tag: {result.stderr}", err=True)
        return False

    return True


# -- Commands --


@app.command()
def hook() -> None:
    """PostToolUse hook entry point. Reads JSON from stdin."""
    try:
        payload = HookPayload.model_validate_json(sys.stdin.read())
    except Exception:
        # Malformed input -- exit silently
        raise typer.Exit(0)

    cmd = payload.tool_input.command

    # Only trigger on `gh pr merge`
    if not re.search(r"gh\s+pr\s+merge", cmd):
        raise typer.Exit(0)

    project_dir = Path.cwd()
    result = evaluate_auto_tag(project_dir)

    if not result.should_tag:
        if result.reason:
            typer.echo(f"[auto-tag] skip: {result.reason}", err=True)
        raise typer.Exit(0)

    if result.manifest_mismatch:
        typer.echo(f"[auto-tag] skip: {result.reason}", err=True)
        raise typer.Exit(0)

    # Create and push tag
    if create_and_push_tag(result.tag_name, result.version):
        typer.echo(
            f"[auto-tag] Created and pushed {result.tag_name}", err=True
        )

    # Always exit 0 -- tagging is advisory, never block
    raise typer.Exit(0)


@app.command()
def ci(
    project_dir: Annotated[
        Optional[str],
        typer.Option("--project-dir", "-d", help="Project root. Defaults to cwd."),
    ] = None,
) -> None:
    """CI entry point. Reads filesystem, no stdin."""
    pdir = Path(project_dir) if project_dir else Path.cwd()
    result = evaluate_auto_tag(pdir)

    if result.manifest_mismatch:
        typer.echo(f"ERROR: {result.reason}", err=True)
        raise typer.Exit(1)

    if not result.should_tag:
        typer.echo(f"[auto-tag] skip: {result.reason}")
        raise typer.Exit(0)

    if create_and_push_tag(result.tag_name, result.version):
        typer.echo(f"[auto-tag] Created and pushed {result.tag_name}")
    else:
        raise typer.Exit(1)

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
