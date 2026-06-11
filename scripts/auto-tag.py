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
from typing import Annotated, Any, Optional

sys.path.insert(0, str(Path(__file__).parent))
from _shared.changelog import get_latest_changelog_version, has_content_under_header  # noqa: E402
from _shared.git_ops import (  # noqa: E402
    get_latest_tag,
    resolve_repo_root,
    shell_command_skeleton,
)

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
    cwd: str = ""
    # PostToolUse fires for FAILED commands too. Shape varies by harness
    # version, so accept anything and interpret it in tool_call_succeeded().
    tool_response: Any = None


# -- Hook trigger / success detection --


_GH_PR_MERGE_RE = re.compile(r"\bgh\s+pr\s+merge\b")


def triggers_auto_tag(command: str) -> bool:
    """True only when `command` actually runs `gh pr merge`.

    Matches against the shell-command skeleton (heredoc bodies and quoted
    spans stripped) so echoed text or a commit message that merely MENTIONS
    "gh pr merge" cannot false-trigger a hook that pushes release tags.
    """
    return _GH_PR_MERGE_RE.search(shell_command_skeleton(command)) is not None


def tool_call_succeeded(tool_response: Any) -> bool:
    """Interpret a PostToolUse tool_response as success or failure.

    PostToolUse fires for failed commands too. Absent or ambiguous response
    data is treated as FAILURE (do nothing) -- never tag on a merge we cannot
    confirm succeeded. Recognized shapes, checked in order:
      - explicit boolean: success / is_error / isError
      - explicit exit code: exit_code / exitCode / returncode / code == 0
      - Bash tool shape: stdout/stderr/interrupted -- interrupted False
        with no error markers is the success shape
    """
    if not isinstance(tool_response, dict):
        return False
    if "success" in tool_response:
        return tool_response["success"] is True
    for key in ("exit_code", "exitCode", "returncode", "code"):
        value = tool_response.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            return value == 0
    for key in ("is_error", "isError"):
        if key in tool_response:
            return tool_response[key] is False
    if "interrupted" in tool_response:
        return tool_response["interrupted"] is False
    return False


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

    # 5. Get latest git tag (in the project's repo, NOT the process cwd --
    # the hook may fire from a different directory than the merged repo)
    latest_tag = get_latest_tag(tag_prefix, cwd=project_dir)
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


# -- Tag creation helpers --


def determine_release_ref(cwd: Path) -> str | None:
    """Resolve the ref a post-merge release tag should point at.

    After `gh pr merge`, the LOCAL checkout is the stale feature branch --
    tagging HEAD would tag the wrong commit. Fetch origin and tag the remote
    default branch head instead. Detection order: origin/HEAD symbolic ref,
    then the current branch's upstream. Returns None (caller logs and skips)
    when neither resolves -- never guess.
    """
    fetch = subprocess.run(
        ["git", "fetch", "origin"],
        capture_output=True, text=True, cwd=cwd,
    )
    if fetch.returncode != 0:
        return None

    result = subprocess.run(
        ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        capture_output=True, text=True, cwd=cwd,
    )
    ref = result.stdout.strip()
    if result.returncode == 0 and ref:
        return ref

    result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
        capture_output=True, text=True, cwd=cwd,
    )
    ref = result.stdout.strip()
    if result.returncode == 0 and ref:
        return ref

    return None


def create_and_push_tag(
    tag_name: str,
    *,
    cwd: Path | None = None,
    ref: str | None = None,
) -> bool:
    """Create an annotated tag (at `ref`, or HEAD) in the repo at `cwd` and
    push it. Returns True on success."""
    tag_cmd = ["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"]
    if ref:
        tag_cmd.append(ref)
    result = subprocess.run(tag_cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        typer.echo(f"Failed to create tag: {result.stderr}", err=True)
        return False

    result = subprocess.run(
        ["git", "push", "origin", tag_name],
        capture_output=True,
        text=True,
        cwd=cwd,
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

    # Only trigger on a command that actually RUNS `gh pr merge` (skeleton
    # match -- echoed text / heredocs must not push release tags)
    if not triggers_auto_tag(cmd):
        raise typer.Exit(0)

    # PostToolUse fires for failed commands too -- only act on confirmed success
    if not tool_call_succeeded(payload.tool_response):
        typer.echo(
            "[auto-tag] skip: could not confirm the merge command succeeded",
            err=True,
        )
        raise typer.Exit(0)

    project_dir = resolve_repo_root(cmd, payload.cwd)
    result = evaluate_auto_tag(project_dir)

    if not result.should_tag:
        if result.reason:
            typer.echo(f"[auto-tag] skip: {result.reason}", err=True)
        raise typer.Exit(0)

    if result.manifest_mismatch:
        typer.echo(f"[auto-tag] skip: {result.reason}", err=True)
        raise typer.Exit(0)

    # The local checkout is the (stale) feature branch after a PR merge --
    # tag the remote default branch head, never local HEAD.
    ref = determine_release_ref(project_dir)
    if ref is None:
        typer.echo(
            "[auto-tag] skip: could not determine the remote default branch"
            " head to tag (fetch/detection failed)",
            err=True,
        )
        raise typer.Exit(0)

    # Create and push tag
    if create_and_push_tag(result.tag_name, cwd=project_dir, ref=ref):
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

    if create_and_push_tag(result.tag_name, cwd=pdir):
        typer.echo(f"[auto-tag] Created and pushed {result.tag_name}")
    else:
        raise typer.Exit(1)

    raise typer.Exit(0)


if __name__ == "__main__":
    app()
