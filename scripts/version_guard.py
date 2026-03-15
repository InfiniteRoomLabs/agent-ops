# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "semver>=3", "pyyaml>=6"]
# ///
"""Guard against version mismatches between manifests, tags, and CHANGELOG.

Usage:
  Human:  uv run version_guard.py check [--project-dir .]
  Hook:   uv run version_guard.py hook  (reads JSON from stdin)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Annotated, Optional

import semver
import typer
import yaml
from pydantic import BaseModel, Field

app = typer.Typer(
    help="Guard against version mismatches on protected branches.",
    no_args_is_help=True,
)

# -- Release commit detection --

RELEASE_COMMIT_RE = re.compile(r"^(release:|chore\(release\):)", re.IGNORECASE)

# -- Pydantic models --


class ManifestSpec(BaseModel):
    path: str
    field: str | None = "version"


class VersionGuardConfig(BaseModel):
    manifests: list[ManifestSpec] = Field(default_factory=list)
    protected_branches: str = r"^(main|master|release/.+)$"
    strategy: str = "manifest-only"
    changelog: str = "CHANGELOG.md"
    tag_prefix: str = "v"
    release_pattern: str = r"^(release:|chore\(release\):)"
    base_version: str | None = None


class ToolInput(BaseModel):
    command: str = ""


class HookPayload(BaseModel):
    tool_name: str = ""
    tool_input: ToolInput = ToolInput()


# -- Config loading --

COMMITLINT_GLOBS = [
    ".commitlintrc",
    ".commitlintrc.json",
    ".commitlintrc.yaml",
    ".commitlintrc.yml",
    ".commitlintrc.js",
    ".commitlintrc.cjs",
    ".commitlintrc.mjs",
    ".commitlintrc.ts",
    "commitlint.config.js",
    "commitlint.config.cjs",
    "commitlint.config.mjs",
    "commitlint.config.ts",
]


def load_config(project_dir: Path) -> VersionGuardConfig:
    """Load config from .version-guard.yaml, with auto-detection fallbacks."""
    config_path = project_dir / ".version-guard.yaml"

    if config_path.is_file():
        raw = yaml.safe_load(config_path.read_text()) or {}
        config = VersionGuardConfig(**raw)
    else:
        config = VersionGuardConfig()

    # Auto-detect conventional commits if commitlint config exists
    if config.strategy == "manifest-only":
        for name in COMMITLINT_GLOBS:
            if (project_dir / name).exists():
                config.strategy = "conventional"
                break

    return config


# -- Manifest detection --

KNOWN_MANIFESTS = [
    ManifestSpec(path="package.json", field="version"),
    ManifestSpec(path="pyproject.toml", field="project.version"),
    ManifestSpec(path="Cargo.toml", field="package.version"),
    ManifestSpec(path="composer.json", field="version"),
    ManifestSpec(path=".claude-plugin/plugin.json", field="version"),
]


def detect_manifests(project_dir: Path) -> list[ManifestSpec]:
    found: list[ManifestSpec] = []
    for spec in KNOWN_MANIFESTS:
        if (project_dir / spec.path).is_file():
            found.append(spec)
    return found


# -- Version reading --

def _traverse(data: dict, dotted_field: str) -> str | None:
    keys = dotted_field.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return str(current) if current is not None else None

def read_manifest_version(project_dir: Path, spec: ManifestSpec) -> str | None:
    filepath = project_dir / spec.path
    if not filepath.is_file():
        return None
    text = filepath.read_text()
    if spec.field is None:
        return text.strip() or None
    if spec.path.endswith(".toml"):
        data = tomllib.loads(text)
    elif spec.path.endswith(".json"):
        data = json.loads(text)
    else:
        return None
    return _traverse(data, spec.field)

def check_manifest_consistency(project_dir: Path, specs: list[ManifestSpec]) -> tuple[bool, str]:
    versions: dict[str, str] = {}
    for spec in specs:
        v = read_manifest_version(project_dir, spec)
        if v is not None:
            versions[spec.path] = v
    if len(versions) <= 1:
        return True, "Single or no manifests found."
    unique = set(versions.values())
    if len(unique) == 1:
        return True, f"All {len(versions)} manifests agree on version {unique.pop()}."
    lines = [f"  {path}: {ver}" for path, ver in sorted(versions.items())]
    return (
        False,
        "BLOCKED: Manifest versions disagree:\n" + "\n".join(lines)
        + "\n\nAll manifest files must declare the same version.",
    )


# -- Git helpers --


def get_current_branch() -> str:
    result = subprocess.run(["git", "branch", "--show-current"], capture_output=True, text=True)
    return result.stdout.strip()


def get_latest_tag_version(prefix: str = "v") -> semver.Version | None:
    result = subprocess.run(
        ["git", "tag", "-l", f"{prefix}*", "--sort=-v:refname"],
        capture_output=True, text=True,
    )
    for line in result.stdout.strip().splitlines():
        tag = line.strip()
        raw = tag[len(prefix):] if tag.startswith(prefix) else tag
        try:
            return semver.Version.parse(raw)
        except ValueError:
            continue
    return None


# -- Conventional commits parser --

COMMIT_TYPE_RE = re.compile(r"^(\w+)(?:\([^)]*\))?(!)?\s*:")
BREAKING_FOOTER_RE = re.compile(r"^BREAKING[ -]CHANGE\s*:", re.MULTILINE)

BUMP_LEVELS = {"major": 3, "minor": 2, "patch": 1, "none": 0}

COMMIT_TYPE_BUMP: dict[str, str] = {
    "fix": "patch",
    "perf": "patch",
    "feat": "minor",
}


def _parse_bump_from_message(message: str) -> str:
    first_line = message.split("\n", 1)[0]
    match = COMMIT_TYPE_RE.match(first_line)
    if not match:
        return "none"
    commit_type = match.group(1).lower()
    has_bang = match.group(2) == "!"
    if has_bang:
        return "major"
    if BREAKING_FOOTER_RE.search(message):
        return "major"
    return COMMIT_TYPE_BUMP.get(commit_type, "none")


def compute_next_version(base: semver.Version, tag_prefix: str = "v") -> semver.Version:
    tag_ref = f"{tag_prefix}{base}"
    result = subprocess.run(
        ["git", "log", f"{tag_ref}..HEAD", "--format=%B---COMMIT_END---", "--max-count=500"],
        capture_output=True, text=True,
    )
    highest = "none"
    for block in result.stdout.split("---COMMIT_END---"):
        msg = block.strip()
        if not msg:
            continue
        bump = _parse_bump_from_message(msg)
        if BUMP_LEVELS[bump] > BUMP_LEVELS[highest]:
            highest = bump
    if highest == "major":
        return base.bump_major()
    elif highest == "minor":
        return base.bump_minor()
    elif highest == "patch":
        return base.bump_patch()
    return base


# -- Evaluation result --


class EvalResult(BaseModel):
    allowed: bool
    message: str = ""


# -- Core evaluation --


def evaluate(
    *,
    config: VersionGuardConfig,
    project_dir: Path,
    commit_message: str,
    is_tag: bool,
    tag_version: str | None = None,
) -> EvalResult:
    """Core enforcement logic. Returns evaluation result."""
    branch = get_current_branch()
    protected_re = re.compile(config.protected_branches)

    # Non-protected branches: exit silently
    if not is_tag and not protected_re.match(branch):
        return EvalResult(allowed=True, message="")

    # Resolve manifests (config or auto-detect)
    specs = config.manifests or detect_manifests(project_dir)

    if not specs:
        # No manifests found: nothing to enforce
        return EvalResult(allowed=True, message="")

    # --- Tag creation checks ---
    if is_tag and tag_version:
        for spec in specs:
            manifest_ver = read_manifest_version(project_dir, spec)
            if manifest_ver and manifest_ver != tag_version:
                return EvalResult(
                    allowed=False,
                    message=(
                        f"BLOCKED: Tag v{tag_version} does not match "
                        f"{spec.path} version {manifest_ver}.\n\n"
                        f"Update {spec.path} to {tag_version} before tagging, "
                        f"or use tag v{manifest_ver} instead."
                    ),
                )
        return EvalResult(allowed=True, message="")

    # --- Commit checks ---
    release_re = re.compile(config.release_pattern, re.IGNORECASE)
    is_release = bool(release_re.match(commit_message))

    # Check manifest consistency (blocks on release commits)
    if len(specs) > 1:
        ok, msg = check_manifest_consistency(project_dir, specs)
        if not ok:
            if is_release:
                return EvalResult(allowed=False, message=msg)
            # Advisory for regular commits
            return EvalResult(allowed=True, message=msg)

    # Read the manifest version (use first manifest as canonical)
    manifest_version_str = None
    for spec in specs:
        v = read_manifest_version(project_dir, spec)
        if v:
            manifest_version_str = v
            break

    # Get latest tag
    latest_tag = get_latest_tag_version(config.tag_prefix)

    # No tags: advisory only, never block
    if latest_tag is None:
        return EvalResult(
            allowed=True,
            message=(
                "[version-guard] INFO: No version tags found in this repository.\n"
                f"Consider creating an initial tag (e.g., git tag -a {config.tag_prefix}0.1.0 "
                f"-m 'Initial version') to enable version tracking."
            ),
        )

    # --- Tier 2: Conventional commits analysis (opt-in) ---
    if config.strategy == "conventional":
        computed = compute_next_version(latest_tag, config.tag_prefix)

        if is_release and manifest_version_str:
            try:
                manifest_ver = semver.Version.parse(manifest_version_str)
            except ValueError:
                return EvalResult(
                    allowed=True,
                    message=f"[version-guard] WARN: Could not parse manifest version '{manifest_version_str}' as semver.",
                )

            if manifest_ver < computed:
                return EvalResult(
                    allowed=False,
                    message=(
                        f"BLOCKED: Manifest version {manifest_ver} is too low.\n"
                        f"Commits since {config.tag_prefix}{latest_tag} require at least {computed}.\n\n"
                        f"Update your manifest(s) to {computed} or higher before releasing."
                    ),
                )

            if manifest_ver > computed:
                return EvalResult(
                    allowed=True,
                    message=(
                        f"[version-guard] WARN: Manifest version {manifest_ver} is higher "
                        f"than computed {computed}.\n"
                        f"Commits since {config.tag_prefix}{latest_tag} only justify {computed}. "
                        f"Proceeding -- ensure the higher version is intentional."
                    ),
                )

            # Exact match
            return EvalResult(allowed=True, message="")

        # Advisory for regular commits on protected branches
        if not is_release and computed > latest_tag:
            return EvalResult(
                allowed=True,
                message=(
                    f"[version-guard] INFO (advisory only -- no action needed):\n"
                    f"Commits since {config.tag_prefix}{latest_tag} suggest "
                    f"next version should be {computed}."
                ),
            )

    # --- Tier 1: Manifest-tag consistency (always on) ---
    if is_release and manifest_version_str:
        try:
            manifest_ver = semver.Version.parse(manifest_version_str)
        except ValueError:
            pass
        else:
            if manifest_ver <= latest_tag:
                return EvalResult(
                    allowed=False,
                    message=(
                        f"BLOCKED: Manifest version {manifest_ver} is not newer than "
                        f"the latest tag {config.tag_prefix}{latest_tag}.\n\n"
                        f"Bump the version in your manifest file(s) above {latest_tag} "
                        f"before releasing."
                    ),
                )

    return EvalResult(allowed=True, message="")


# -- Commands --


@app.command()
def check(
    project_dir: Annotated[
        Optional[str],
        typer.Option("--project-dir", "-d", help="Project root. Defaults to cwd."),
    ] = None,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show what would happen without blocking."),
    ] = False,
) -> None:
    """Check version consistency for the current project."""
    pdir = Path(project_dir) if project_dir else Path.cwd()
    config = load_config(pdir)

    # For CLI check, simulate a release commit to trigger full validation
    result = evaluate(
        config=config,
        project_dir=pdir,
        commit_message="release: check",
        is_tag=False,
    )

    if result.message:
        typer.echo(result.message)

    if not result.allowed and not dry_run:
        raise typer.Exit(1)
    raise typer.Exit(0)


@app.command()
def hook() -> None:
    """Claude Code PreToolUse hook entry point. Reads JSON from stdin."""
    payload = HookPayload.model_validate_json(sys.stdin.read())
    cmd = payload.tool_input.command

    is_commit = bool(re.search(r"git\s+commit", cmd))
    is_tag_cmd = bool(re.search(r"git\s+tag\s", cmd))

    if not is_commit and not is_tag_cmd:
        raise typer.Exit(0)

    # Block combined add+commit
    if is_commit and re.search(r"git\s+add\b", cmd):
        typer.echo(
            "BLOCKED: Run 'git add' and 'git commit' as separate Bash calls.\n"
            "The version guard needs to inspect staged files between the two steps.\n"
            "Stage your files first, then commit in a follow-up command.",
            err=True,
        )
        raise typer.Exit(2)

    project_dir = Path.cwd()
    config = load_config(project_dir)

    # Extract commit message for release detection.
    # Handles both -m "msg" and HEREDOC patterns (cat <<'EOF' ... EOF).
    # For release detection we only need to know if the message starts with
    # "release:" or "chore(release):" -- so search the entire command string
    # as a heuristic rather than trying to precisely parse shell quoting.
    commit_message = ""
    if is_commit:
        # Try direct -m extraction first
        msg_match = re.search(r"""-m\s+(['"])(.*?)\1""", cmd)
        if msg_match:
            commit_message = msg_match.group(2)
        elif re.search(r"release:|chore\(release\):", cmd, re.IGNORECASE):
            # HEREDOC or other format -- extract the release line
            release_match = re.search(
                r"((?:release:|chore\(release\):)\s*\S.*)", cmd, re.IGNORECASE
            )
            commit_message = release_match.group(1) if release_match else ""

    # Extract tag version for tag checks.
    # Parse the positional argument to `git tag` by finding the tag prefix
    # anywhere in the command after "git tag".
    tag_version = None
    if is_tag_cmd:
        # Find tag_prefix followed by a semver-like string
        tag_match = re.search(
            re.escape(config.tag_prefix) + r"(\d+\.\d+\.\d+\S*)",
            cmd,
        )
        if tag_match:
            tag_version = tag_match.group(1)

    result = evaluate(
        config=config,
        project_dir=project_dir,
        commit_message=commit_message,
        is_tag=is_tag_cmd,
        tag_version=tag_version,
    )

    if result.message:
        if result.allowed:
            # Advisory: print to stderr so Claude sees it but it doesn't block
            typer.echo(result.message, err=True)
        else:
            typer.echo(result.message, err=True)

    raise typer.Exit(2 if not result.allowed else 0)


if __name__ == "__main__":
    app()
