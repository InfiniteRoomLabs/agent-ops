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


if __name__ == "__main__":
    app()
