# Version Guard Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic PreToolUse hook (`version-guard.py`) that enforces semver consistency between manifest files, git tags, and CHANGELOG entries on protected branches, shipping as part of the agent-ops plugin for use in any repo.

**Architecture:** Two-tier enforcement system. Tier 1 (always on) ensures manifests, tags, and CHANGELOG agree with each other. Tier 2 (opt-in via config or auto-detection) uses conventional commits to compute expected versions and validates manifest versions against them. Advisory for regular commits on protected branches; mandatory for release commits and tag creation. Follows the exact same pattern as `scripts/changelog-guard.py` (PEP 723, Typer, Pydantic, exit 2 = block).

**Tech Stack:** Python 3.11+ (via `uv run`), Typer (CLI), Pydantic (models/validation), `semver` (version comparison), PyYAML (config parsing), pytest (testing)

**Design Decisions (locked in by CTO/VP Eng/DevOps Mgr panel review):**
- Asymmetric version comparison: block if manifest < computed, warn if manifest > computed
- Release commit pattern: `^release:` or `^chore\(release\):` only
- First-release bootstrap: advisory "no tags found" + exit 0, no blocking
- Conventional commits: opt-in (Tier 2), not default
- No advisory output on non-protected branches (exit 0 silently)
- Config via `.version-guard.yaml` in project root, auto-detection as fallback
- Monorepo and pre-release versions: deferred to future phases
- `semver` PyPI library for version comparison (not hand-rolled)

**Reference files:**
- `scripts/changelog-guard.py` -- pattern to follow (131 lines)
- `hooks/hooks.json` -- where the hook gets registered
- `registry.yaml` -- must be updated with new script entry
- `skills/release-prep/SKILL.md` -- complementary skill (guides releases, version-guard enforces them)

---

## File Inventory

All paths relative to repo root (`agent-ops/`).

| Action | Path | Purpose |
|--------|------|---------|
| CREATE | `scripts/version_guard.py` | Main script -- all enforcement logic |
| CREATE | `tests/test_version_guard.py` | All tests |
| CREATE | `tests/conftest.py` | Shared test fixtures (git repo scaffolding) |
| MODIFY | `hooks/hooks.json:30-41` | Add version-guard to PreToolUse Bash matcher |
| MODIFY | `registry.yaml` | Add version-guard script entry |

Five files total. The script is the only production code. Everything else is tests, config, and registration.

---

## Key Design Decisions for Implementer

1. **Single file script.** Like `changelog-guard.py`, the version guard is a single Python file with PEP 723 inline dependencies. No package structure, no `pyproject.toml` for the script itself. Tests get their own `pyproject.toml` (or use `uv run --with` for test deps).

2. **Two command entry points.** `check` for human/CI use (exit 0/1, stdout), `hook` for Claude Code PreToolUse (exit 0/2, stderr). Same `evaluate()` core.

3. **Config loading order.** Read `.version-guard.yaml` from `$CLAUDE_PROJECT_DIR` (or cwd). If absent, auto-detect manifests and use defaults. Config is optional, never required.

4. **Manifest auto-detection precedence.** Scan project root for (in order): `package.json`, `pyproject.toml`, `Cargo.toml`, `composer.json`, `.claude-plugin/plugin.json`. Stop at first found unless config overrides. Do NOT auto-detect bare `VERSION` files (too ambiguous).

5. **Conventional commits opt-in detection.** Enable Tier 2 if any of: (a) `.version-guard.yaml` has `strategy: conventional`, (b) a `.commitlintrc*` or `commitlint.config.*` file exists, (c) config explicitly sets `conventional_commits: true`.

6. **The `git add` + `git commit` split guard.** Port from `changelog-guard.py` lines 110-117. Both hooks need it.

7. **Version extraction from git tags.** Use `git tag -l 'v*' --sort=-v:refname` to find latest semver tag. Strip `v` prefix. Parse with `semver.Version.parse()`. If no tags match, computed version is `None`.

8. **Conventional commits parser.** Parse `git log <tag>..HEAD --format=%H%n%B%n---COMMIT_END---`. For each commit: extract type from first line (`^(\w+)(?:\(.+?\))?!?:`), check for `!` suffix or `BREAKING CHANGE:` in body. Map: `fix:` = patch, `feat:` = minor, `!` or `BREAKING CHANGE:` = major. Take highest bump. Apply to base version.

---

## Chunk 1: Test Infrastructure and Core Models

### Task 1: Test scaffolding

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/test_version_guard.py` (initially empty)

- [ ] **Step 1: Create conftest.py with git repo fixture**

```python
"""Shared fixtures for version-guard tests."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture()
def git_repo(tmp_path: Path) -> Generator[Path, None, None]:
    """Create a temporary git repo with an initial commit on 'main' branch."""
    prev = os.getcwd()
    os.chdir(tmp_path)
    subprocess.run(["git", "init", "-b", "main"], check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        check=True,
        capture_output=True,
    )
    (tmp_path / "README.md").write_text("# test\n")
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: initial commit"],
        check=True,
        capture_output=True,
    )
    yield tmp_path
    os.chdir(prev)


@pytest.fixture()
def tagged_repo(git_repo: Path) -> Path:
    """Git repo with a v1.0.0 tag on the initial commit."""
    subprocess.run(
        ["git", "tag", "-a", "v1.0.0", "-m", "Release v1.0.0"],
        check=True,
        capture_output=True,
    )
    return git_repo


@pytest.fixture()
def repo_with_manifest(tagged_repo: Path) -> Path:
    """Tagged repo with a package.json at version 1.0.0."""
    (tagged_repo / "package.json").write_text('{\n  "version": "1.0.0"\n}\n')
    subprocess.run(["git", "add", "."], check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "chore: add package.json"],
        check=True,
        capture_output=True,
    )
    return tagged_repo
```

- [ ] **Step 2: Create empty test file**

```python
"""Tests for version-guard.py."""
```

- [ ] **Step 3: Verify pytest discovers the fixtures**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run --with pytest pytest tests/test_version_guard.py --collect-only`
Expected: "no tests ran" (0 items collected), no import errors.

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py tests/test_version_guard.py
git commit -m "chore: scaffold version-guard test infrastructure"
```

---

### Task 2: Pydantic models and config loading

**Files:**
- Create: `scripts/version_guard.py` (initial structure)
- Test: `tests/test_version_guard.py`

- [ ] **Step 1: Write failing tests for config loading**

Add to `tests/test_version_guard.py`:

```python
import json
from pathlib import Path

import pytest


def test_load_config_from_yaml(git_repo: Path) -> None:
    """Config file overrides auto-detection."""
    from version_guard import load_config

    (git_repo / ".version-guard.yaml").write_text(
        "manifests:\n"
        "  - path: custom/version.json\n"
        "    field: version\n"
        "protected_branches: '^(main|develop)$'\n"
        "strategy: conventional\n"
    )
    config = load_config(git_repo)
    assert len(config.manifests) == 1
    assert config.manifests[0].path == "custom/version.json"
    assert config.manifests[0].field == "version"
    assert config.protected_branches == "^(main|develop)$"
    assert config.strategy == "conventional"


def test_load_config_defaults_when_no_yaml(git_repo: Path) -> None:
    """No config file means sensible defaults."""
    from version_guard import load_config

    config = load_config(git_repo)
    assert config.strategy == "manifest-only"
    assert config.protected_branches == "^(main|master|release/.+)$"
    assert config.manifests == []  # empty = auto-detect
    assert config.changelog == "CHANGELOG.md"
    assert config.tag_prefix == "v"


def test_load_config_detects_commitlint(git_repo: Path) -> None:
    """Presence of commitlint config upgrades strategy to conventional."""
    from version_guard import load_config

    (git_repo / ".commitlintrc.json").write_text("{}")
    config = load_config(git_repo)
    assert config.strategy == "conventional"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'version_guard'`

- [ ] **Step 3: Write the script skeleton with config models**

Create `scripts/version_guard.py`:

```python
# /// script
# dependencies = ["pydantic>=2", "typer>=0.15", "semver>=3", "pyyaml>=6"]
# ///
"""Guard against version mismatches between manifests, tags, and CHANGELOG.

Usage:
  Human:  uv run version_guard.py check [--project-dir .]
  Hook:   uv run version_guard.py hook  (reads JSON from stdin)
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Annotated, Optional

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
    strategy: str = "manifest-only"  # "manifest-only" or "conventional"
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


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/version_guard.py tests/test_version_guard.py
git commit -m "feat(version-guard): add config models and YAML loading"
```

---

## Chunk 2: Manifest Detection and Version Reading

### Task 3: Manifest auto-detection

**Files:**
- Modify: `scripts/version_guard.py`
- Test: `tests/test_version_guard.py`

- [ ] **Step 1: Write failing tests for manifest detection**

Add to `tests/test_version_guard.py`:

```python
def test_detect_package_json(git_repo: Path) -> None:
    """Auto-detects package.json at project root."""
    from version_guard import detect_manifests

    (git_repo / "package.json").write_text('{"version": "1.2.3"}')
    manifests = detect_manifests(git_repo)
    assert len(manifests) == 1
    assert manifests[0].path == "package.json"
    assert manifests[0].field == "version"


def test_detect_pyproject_toml(git_repo: Path) -> None:
    """Auto-detects pyproject.toml at project root."""
    from version_guard import detect_manifests

    (git_repo / "pyproject.toml").write_text(
        '[project]\nname = "foo"\nversion = "0.1.0"\n'
    )
    manifests = detect_manifests(git_repo)
    assert len(manifests) == 1
    assert manifests[0].path == "pyproject.toml"


def test_detect_plugin_json(git_repo: Path) -> None:
    """Auto-detects .claude-plugin/plugin.json."""
    from version_guard import detect_manifests

    plugin_dir = git_repo / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"version": "1.0.0"}')
    manifests = detect_manifests(git_repo)
    assert len(manifests) == 1
    assert manifests[0].path == ".claude-plugin/plugin.json"


def test_detect_no_manifests(git_repo: Path) -> None:
    """No known manifests returns empty list."""
    from version_guard import detect_manifests

    manifests = detect_manifests(git_repo)
    assert manifests == []


def test_detect_multiple_manifests(git_repo: Path) -> None:
    """Detects all known manifests present."""
    from version_guard import detect_manifests

    (git_repo / "package.json").write_text('{"version": "1.0.0"}')
    (git_repo / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1.0.0"\n'
    )
    manifests = detect_manifests(git_repo)
    assert len(manifests) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py::test_detect_package_json -v`
Expected: FAIL with `cannot import name 'detect_manifests'`

- [ ] **Step 3: Implement detect_manifests()**

Add to `scripts/version_guard.py` after config loading section:

```python
# -- Manifest detection --

KNOWN_MANIFESTS = [
    ManifestSpec(path="package.json", field="version"),
    ManifestSpec(path="pyproject.toml", field="project.version"),
    ManifestSpec(path="Cargo.toml", field="package.version"),
    ManifestSpec(path="composer.json", field="version"),
    ManifestSpec(path=".claude-plugin/plugin.json", field="version"),
]


def detect_manifests(project_dir: Path) -> list[ManifestSpec]:
    """Scan project root for known manifest files."""
    found: list[ManifestSpec] = []
    for spec in KNOWN_MANIFESTS:
        if (project_dir / spec.path).is_file():
            found.append(spec)
    return found
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k detect`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/version_guard.py tests/test_version_guard.py
git commit -m "feat(version-guard): add manifest auto-detection"
```

---

### Task 4: Read version from manifest files

**Files:**
- Modify: `scripts/version_guard.py`
- Test: `tests/test_version_guard.py`

- [ ] **Step 1: Write failing tests for version reading**

Add to `tests/test_version_guard.py`:

```python
def test_read_version_from_json(git_repo: Path) -> None:
    """Reads version from a JSON manifest."""
    from version_guard import read_manifest_version

    (git_repo / "package.json").write_text('{"version": "2.1.0"}')
    version = read_manifest_version(
        git_repo, ManifestSpec(path="package.json", field="version")
    )
    assert version == "2.1.0"


def test_read_version_from_toml(git_repo: Path) -> None:
    """Reads nested version from TOML manifest."""
    from version_guard import read_manifest_version

    (git_repo / "pyproject.toml").write_text(
        '[project]\nname = "foo"\nversion = "3.0.1"\n'
    )
    version = read_manifest_version(
        git_repo, ManifestSpec(path="pyproject.toml", field="project.version")
    )
    assert version == "3.0.1"


def test_read_version_missing_file(git_repo: Path) -> None:
    """Returns None for missing manifest file."""
    from version_guard import read_manifest_version

    version = read_manifest_version(
        git_repo, ManifestSpec(path="nope.json", field="version")
    )
    assert version is None


def test_read_version_missing_field(git_repo: Path) -> None:
    """Returns None if field does not exist in manifest."""
    from version_guard import read_manifest_version

    (git_repo / "package.json").write_text('{"name": "foo"}')
    version = read_manifest_version(
        git_repo, ManifestSpec(path="package.json", field="version")
    )
    assert version is None


def test_manifest_consistency_all_match(git_repo: Path) -> None:
    """All manifests agree on the same version."""
    from version_guard import check_manifest_consistency

    (git_repo / "package.json").write_text('{"version": "1.5.0"}')
    plugin_dir = git_repo / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"version": "1.5.0"}')
    specs = [
        ManifestSpec(path="package.json", field="version"),
        ManifestSpec(path=".claude-plugin/plugin.json", field="version"),
    ]
    ok, msg = check_manifest_consistency(git_repo, specs)
    assert ok is True


def test_manifest_consistency_mismatch(git_repo: Path) -> None:
    """Detects when manifests disagree."""
    from version_guard import check_manifest_consistency

    (git_repo / "package.json").write_text('{"version": "1.5.0"}')
    plugin_dir = git_repo / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"version": "1.4.0"}')
    specs = [
        ManifestSpec(path="package.json", field="version"),
        ManifestSpec(path=".claude-plugin/plugin.json", field="version"),
    ]
    ok, msg = check_manifest_consistency(git_repo, specs)
    assert ok is False
    assert "1.5.0" in msg
    assert "1.4.0" in msg
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "read_version or manifest_consistency"`
Expected: FAIL with `cannot import name 'read_manifest_version'`

- [ ] **Step 3: Implement version reading and consistency check**

Add to `scripts/version_guard.py`:

```python
import json
import tomllib


# -- Version reading --


def _traverse(data: dict, dotted_field: str) -> str | None:
    """Walk a nested dict by dotted key path. Returns None if missing."""
    keys = dotted_field.split(".")
    current = data
    for key in keys:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return str(current) if current is not None else None


def read_manifest_version(
    project_dir: Path, spec: ManifestSpec
) -> str | None:
    """Read the version string from a single manifest file."""
    filepath = project_dir / spec.path
    if not filepath.is_file():
        return None

    text = filepath.read_text()

    if spec.field is None:
        # Entire file content is the version (e.g., VERSION file)
        return text.strip() or None

    if spec.path.endswith(".toml"):
        data = tomllib.loads(text)
    elif spec.path.endswith(".json"):
        data = json.loads(text)
    else:
        return None

    return _traverse(data, spec.field)


def check_manifest_consistency(
    project_dir: Path, specs: list[ManifestSpec]
) -> tuple[bool, str]:
    """Check that all manifests report the same version."""
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
```

Note: Python 3.11+ is required (tomllib is stdlib). No tomli fallback needed.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "read_version or manifest_consistency"`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/version_guard.py tests/test_version_guard.py
git commit -m "feat(version-guard): add manifest version reading and consistency check"
```

---

## Chunk 3: Git Tag Reading and Conventional Commits Parser

### Task 5: Git tag version detection

**Files:**
- Modify: `scripts/version_guard.py`
- Test: `tests/test_version_guard.py`

- [ ] **Step 1: Write failing tests for tag reading**

Add to `tests/test_version_guard.py`:

```python
import subprocess as sp

import semver


def test_get_latest_tag_version(tagged_repo: Path) -> None:
    """Reads the latest semver tag."""
    from version_guard import get_latest_tag_version

    ver = get_latest_tag_version("v")
    assert ver == semver.Version.parse("1.0.0")


def test_get_latest_tag_version_no_tags(git_repo: Path) -> None:
    """Returns None when no version tags exist."""
    from version_guard import get_latest_tag_version

    ver = get_latest_tag_version("v")
    assert ver is None


def test_get_latest_tag_version_multiple(tagged_repo: Path) -> None:
    """Returns the highest semver tag, not just the latest chronologically."""
    from version_guard import get_latest_tag_version

    (tagged_repo / "a.txt").write_text("a")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "feat: add a"], check=True, capture_output=True)
    sp.run(
        ["git", "tag", "-a", "v1.1.0", "-m", "v1.1.0"],
        check=True,
        capture_output=True,
    )
    ver = get_latest_tag_version("v")
    assert ver == semver.Version.parse("1.1.0")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "get_latest_tag"`
Expected: FAIL with `cannot import name 'get_latest_tag_version'`

- [ ] **Step 3: Implement get_latest_tag_version()**

Add to `scripts/version_guard.py`:

```python
import semver


# -- Git helpers --


def get_current_branch() -> str:
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def get_latest_tag_version(prefix: str = "v") -> semver.Version | None:
    """Find the latest semver tag in the repo. Returns None if no tags."""
    result = subprocess.run(
        ["git", "tag", "-l", f"{prefix}*", "--sort=-v:refname"],
        capture_output=True,
        text=True,
    )
    for line in result.stdout.strip().splitlines():
        tag = line.strip()
        raw = tag[len(prefix):] if tag.startswith(prefix) else tag
        try:
            return semver.Version.parse(raw)
        except ValueError:
            continue
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "get_latest_tag"`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/version_guard.py tests/test_version_guard.py
git commit -m "feat(version-guard): add git tag version detection"
```

---

### Task 6: Conventional commits parser (Tier 2)

**Files:**
- Modify: `scripts/version_guard.py`
- Test: `tests/test_version_guard.py`

- [ ] **Step 1: Write failing tests for commit parsing**

Add to `tests/test_version_guard.py`:

```python
def test_compute_bump_from_fix(tagged_repo: Path) -> None:
    """fix: commits produce a PATCH bump."""
    from version_guard import compute_next_version

    (tagged_repo / "b.txt").write_text("b")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "fix: correct typo"], check=True, capture_output=True)
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.0.1")


def test_compute_bump_from_feat(tagged_repo: Path) -> None:
    """feat: commits produce a MINOR bump."""
    from version_guard import compute_next_version

    (tagged_repo / "c.txt").write_text("c")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "feat: add widget"], check=True, capture_output=True)
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.1.0")


def test_compute_bump_from_breaking_bang(tagged_repo: Path) -> None:
    """feat!: commits produce a MAJOR bump."""
    from version_guard import compute_next_version

    (tagged_repo / "d.txt").write_text("d")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(
        ["git", "commit", "-m", "feat!: redesign API"],
        check=True,
        capture_output=True,
    )
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("2.0.0")


def test_compute_bump_from_breaking_footer(tagged_repo: Path) -> None:
    """BREAKING CHANGE footer produces a MAJOR bump."""
    from version_guard import compute_next_version

    (tagged_repo / "e.txt").write_text("e")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(
        ["git", "commit", "-m", "feat: new thing\n\nBREAKING CHANGE: removed old API"],
        check=True,
        capture_output=True,
    )
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("2.0.0")


def test_compute_bump_highest_wins(tagged_repo: Path) -> None:
    """Multiple commits: the highest bump level wins."""
    from version_guard import compute_next_version

    for name, msg in [("f.txt", "fix: a"), ("g.txt", "feat: b"), ("h.txt", "fix: c")]:
        (tagged_repo / name).write_text(name)
        sp.run(["git", "add", "."], check=True, capture_output=True)
        sp.run(["git", "commit", "-m", msg], check=True, capture_output=True)

    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.1.0")


def test_compute_bump_no_bumping_commits(tagged_repo: Path) -> None:
    """chore/docs commits produce no bump (returns base version)."""
    from version_guard import compute_next_version

    (tagged_repo / "i.txt").write_text("i")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(
        ["git", "commit", "-m", "chore: update readme"],
        check=True,
        capture_output=True,
    )
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.0.0")


def test_compute_bump_no_commits_since_tag(tagged_repo: Path) -> None:
    """No commits since tag returns the base version."""
    from version_guard import compute_next_version

    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.0.0")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "compute_bump"`
Expected: FAIL with `cannot import name 'compute_next_version'`

- [ ] **Step 3: Implement conventional commits parser**

Add to `scripts/version_guard.py`:

```python
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
    """Determine bump level from a single commit message. Returns bump string."""
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


def compute_next_version(
    base: semver.Version, tag_prefix: str = "v"
) -> semver.Version:
    """Compute the next version from conventional commits since the last tag."""
    tag_ref = f"{tag_prefix}{base}"
    result = subprocess.run(
        [
            "git", "log", f"{tag_ref}..HEAD",
            "--format=%B---COMMIT_END---",
            "--max-count=500",
        ],
        capture_output=True,
        text=True,
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "compute_bump"`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add scripts/version_guard.py tests/test_version_guard.py
git commit -m "feat(version-guard): add conventional commits parser"
```

---

## Chunk 4: Core Evaluation Logic

### Task 7: The evaluate() function -- Tier 1 (manifest-only) and Tier 2 (conventional)

**Files:**
- Modify: `scripts/version_guard.py`
- Test: `tests/test_version_guard.py`

- [ ] **Step 1: Write failing tests for evaluate()**

Add to `tests/test_version_guard.py`:

```python
def test_evaluate_non_protected_branch(git_repo: Path) -> None:
    """Non-protected branches exit silently (no output)."""
    from version_guard import evaluate, VersionGuardConfig

    sp.run(["git", "checkout", "-b", "feature/foo"], check=True, capture_output=True)
    config = VersionGuardConfig()
    result = evaluate(
        config=config,
        project_dir=git_repo,
        commit_message="feat: something",
        is_tag=False,
    )
    assert result.allowed is True
    assert result.message == ""


def test_evaluate_release_commit_version_match(repo_with_manifest: Path) -> None:
    """Release commit with matching manifest version passes."""
    from version_guard import evaluate, VersionGuardConfig, ManifestSpec

    # Bump manifest to 1.1.0 and add a feat commit
    (repo_with_manifest / "new.txt").write_text("x")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "feat: add new"], check=True, capture_output=True)
    (repo_with_manifest / "package.json").write_text('{"version": "1.1.0"}')
    sp.run(["git", "add", "."], check=True, capture_output=True)

    config = VersionGuardConfig(
        strategy="conventional",
        manifests=[ManifestSpec(path="package.json", field="version")],
    )
    result = evaluate(
        config=config,
        project_dir=repo_with_manifest,
        commit_message="release: v1.1.0",
        is_tag=False,
    )
    assert result.allowed is True


def test_evaluate_release_commit_version_too_low(repo_with_manifest: Path) -> None:
    """Release commit with manifest version lower than computed blocks."""
    from version_guard import evaluate, VersionGuardConfig, ManifestSpec

    (repo_with_manifest / "new.txt").write_text("x")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "feat: add new"], check=True, capture_output=True)
    # Manifest says 1.0.1 but feat commit requires at least 1.1.0
    (repo_with_manifest / "package.json").write_text('{"version": "1.0.1"}')
    sp.run(["git", "add", "."], check=True, capture_output=True)

    config = VersionGuardConfig(
        strategy="conventional",
        manifests=[ManifestSpec(path="package.json", field="version")],
    )
    result = evaluate(
        config=config,
        project_dir=repo_with_manifest,
        commit_message="release: v1.0.1",
        is_tag=False,
    )
    assert result.allowed is False
    assert "too low" in result.message.lower() or "1.1.0" in result.message


def test_evaluate_release_commit_version_higher_warns(
    repo_with_manifest: Path,
) -> None:
    """Release commit with manifest version higher than computed warns but allows."""
    from version_guard import evaluate, VersionGuardConfig, ManifestSpec

    (repo_with_manifest / "new.txt").write_text("x")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "fix: small fix"], check=True, capture_output=True)
    # Manifest says 2.0.0 but fix commit only requires 1.0.1
    (repo_with_manifest / "package.json").write_text('{"version": "2.0.0"}')
    sp.run(["git", "add", "."], check=True, capture_output=True)

    config = VersionGuardConfig(
        strategy="conventional",
        manifests=[ManifestSpec(path="package.json", field="version")],
    )
    result = evaluate(
        config=config,
        project_dir=repo_with_manifest,
        commit_message="release: v2.0.0",
        is_tag=False,
    )
    assert result.allowed is True
    assert "higher" in result.message.lower()


def test_evaluate_tag_matches_manifest(repo_with_manifest: Path) -> None:
    """Tag creation matching manifest version passes."""
    from version_guard import evaluate, VersionGuardConfig, ManifestSpec

    config = VersionGuardConfig(
        manifests=[ManifestSpec(path="package.json", field="version")],
    )
    result = evaluate(
        config=config,
        project_dir=repo_with_manifest,
        commit_message="",
        is_tag=True,
        tag_version="1.0.0",
    )
    assert result.allowed is True


def test_evaluate_tag_mismatches_manifest(repo_with_manifest: Path) -> None:
    """Tag creation not matching manifest version blocks."""
    from version_guard import evaluate, VersionGuardConfig, ManifestSpec

    config = VersionGuardConfig(
        manifests=[ManifestSpec(path="package.json", field="version")],
    )
    result = evaluate(
        config=config,
        project_dir=repo_with_manifest,
        commit_message="",
        is_tag=True,
        tag_version="2.0.0",
    )
    assert result.allowed is False
    assert "2.0.0" in result.message
    assert "1.0.0" in result.message


def test_evaluate_manifest_consistency_blocks(git_repo: Path) -> None:
    """Manifests disagreeing blocks on release commits."""
    from version_guard import evaluate, VersionGuardConfig, ManifestSpec

    (git_repo / "package.json").write_text('{"version": "1.0.0"}')
    plugin_dir = git_repo / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"version": "0.9.0"}')
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(
        ["git", "tag", "-a", "v1.0.0", "-m", "v1.0.0"],
        check=True,
        capture_output=True,
    )

    config = VersionGuardConfig(
        manifests=[
            ManifestSpec(path="package.json", field="version"),
            ManifestSpec(path=".claude-plugin/plugin.json", field="version"),
        ],
    )
    result = evaluate(
        config=config,
        project_dir=git_repo,
        commit_message="release: v1.0.0",
        is_tag=False,
    )
    assert result.allowed is False
    assert "disagree" in result.message.lower()


def test_evaluate_no_tags_advisory(git_repo: Path) -> None:
    """Repos with no tags get an advisory, never block."""
    from version_guard import evaluate, VersionGuardConfig

    config = VersionGuardConfig(strategy="conventional")
    result = evaluate(
        config=config,
        project_dir=git_repo,
        commit_message="release: v1.0.0",
        is_tag=False,
    )
    assert result.allowed is True
    assert "no version tags" in result.message.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "evaluate"`
Expected: FAIL with `cannot import name 'evaluate'`

- [ ] **Step 3: Implement the evaluate() function**

Add to `scripts/version_guard.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "evaluate"`
Expected: 9 passed

- [ ] **Step 5: Run all tests together**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v`
Expected: All tests pass (20+ tests)

- [ ] **Step 6: Commit**

```bash
git add scripts/version_guard.py tests/test_version_guard.py
git commit -m "feat(version-guard): add core evaluate() with Tier 1 and Tier 2 enforcement"
```

---

## Chunk 5: CLI and Hook Integration

### Task 8: Typer CLI commands (check + hook)

**Files:**
- Modify: `scripts/version_guard.py`
- Test: `tests/test_version_guard.py`

- [ ] **Step 1: Write failing tests for CLI commands**

Add to `tests/test_version_guard.py`:

```python
from typer.testing import CliRunner


def test_check_command_passes(repo_with_manifest: Path) -> None:
    """check command exits 0 when manifests are consistent and version > tag."""
    from version_guard import app

    # Bump manifest ahead of the tag so Tier 1 doesn't block
    (repo_with_manifest / "package.json").write_text('{"version": "1.1.0"}')
    sp.run(["git", "add", "."], check=True, capture_output=True)

    runner = CliRunner()
    result = runner.invoke(app, ["check", "--project-dir", str(repo_with_manifest)])
    assert result.exit_code == 0


def test_hook_ignores_non_commit(git_repo: Path) -> None:
    """Hook exits 0 for non-commit Bash commands."""
    from version_guard import app

    runner = CliRunner()
    result = runner.invoke(app, ["hook"], input='{"tool_name": "Bash", "tool_input": {"command": "ls -la"}}')
    assert result.exit_code == 0


def test_hook_blocks_combined_add_commit(git_repo: Path) -> None:
    """Hook blocks combined git add + git commit."""
    from version_guard import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["hook"],
        input='{"tool_name": "Bash", "tool_input": {"command": "git add . && git commit -m \\"release: v1.0.0\\""}}',
    )
    assert result.exit_code == 2


def test_hook_ignores_non_git(git_repo: Path) -> None:
    """Hook exits 0 for non-git operations."""
    from version_guard import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["hook"],
        input='{"tool_name": "Bash", "tool_input": {"command": "echo hello"}}',
    )
    assert result.exit_code == 0


def test_hook_handles_git_tag_a_pattern(repo_with_manifest: Path) -> None:
    """Hook correctly parses git tag -a v1.0.0 -m 'msg' (the most common form)."""
    from version_guard import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["hook"],
        input='{"tool_name": "Bash", "tool_input": {"command": "git tag -a v1.0.0 -m \\"Release v1.0.0\\""}}',
    )
    # Tag matches manifest (1.0.0) so should pass
    assert result.exit_code == 0


def test_hook_handles_heredoc_release_commit(repo_with_manifest: Path) -> None:
    r"""Hook detects release: in HEREDOC-style commit messages."""
    from version_guard import app

    heredoc_cmd = (
        'git commit -m "$(cat <<\'EOF\'\n'
        'release: v1.1.0\n'
        '\n'
        'Co-Authored-By: Test\n'
        'EOF\n'
        ')"'
    )
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["hook"],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": heredoc_cmd}}),
    )
    # On main with conventional strategy not active by default,
    # release commit triggers Tier 1 checks
    # Manifest is 1.0.0, tag is 1.0.0 -- should block (not newer)
    # But without .version-guard.yaml, strategy is manifest-only and
    # Tier 1 release check fires: manifest 1.0.0 <= tag 1.0.0 = BLOCK
    assert result.exit_code == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "check_command or hook_"`
Expected: FAIL

- [ ] **Step 3: Implement check and hook commands**

Add to `scripts/version_guard.py` (replace the `if __name__` block):

```python
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
    branch = get_current_branch()

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
        msg_match = re.search(r'''-m\s+(['"])(.*?)\1''', cmd)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v -k "check_command or hook_"`
Expected: 4 passed

- [ ] **Step 5: Run full test suite**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v`
Expected: All tests pass

- [ ] **Step 6: Commit**

```bash
git add scripts/version_guard.py tests/test_version_guard.py
git commit -m "feat(version-guard): add check and hook CLI commands"
```

---

### Task 9: Hook registration and registry update

**Files:**
- Modify: `hooks/hooks.json:30-41`
- Modify: `registry.yaml`

- [ ] **Step 1: Add version-guard to hooks.json**

The version-guard hook runs alongside changelog-guard in the same PreToolUse Bash matcher. Add it as a second entry in the `hooks` array:

Update `hooks/hooks.json` -- replace the PreToolUse section:

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/changelog-guard.py hook",
        "timeout": 10
      },
      {
        "type": "command",
        "command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/version_guard.py hook",
        "timeout": 15
      }
    ]
  }
]
```

Note: 15 second timeout for version-guard (needs to run git log and parse manifests).

- [ ] **Step 2: Update registry.yaml**

Add under the `skills:` section (after `release-prep`):

```yaml
scripts:
  - name: version-guard
    description: "PreToolUse hook enforcing semver consistency between manifests, tags, and CHANGELOG on protected branches"
    tags:
      function: [engineering]
      scenario: [versioning, release-management]
      custom: [semver, conventional-commits, enforcement]
```

- [ ] **Step 3: Verify hooks.json is valid JSON**

Run: `python3 -c "import json; json.load(open('hooks/hooks.json')); print('valid')"`
Expected: `valid`

- [ ] **Step 4: Commit**

```bash
git add hooks/hooks.json registry.yaml
git commit -m "feat(version-guard): register hook in hooks.json and registry"
```

---

## Chunk 6: Final Verification

### Task 10: End-to-end smoke test

- [ ] **Step 1: Run the full test suite one final time**

Run: `cd /home/deathnerd/projects/infinite-room-labs/agent-ops && PYTHONPATH=scripts uv run --with pytest --with pydantic --with typer --with semver --with pyyaml pytest tests/test_version_guard.py -v`
Expected: All tests pass (24+ tests)

- [ ] **Step 2: Manual smoke test of the hook command**

Run: `echo '{"tool_name": "Bash", "tool_input": {"command": "git commit -m \"feat: add widget\""}}' | uv run scripts/version_guard.py hook; echo "exit: $?"`
Expected: exit 0 (regular commit on main, advisory only)

- [ ] **Step 3: Manual smoke test of the check command**

Run: `uv run scripts/version_guard.py check --project-dir .`
Expected: Output about current version state

- [ ] **Step 4: Verify script runs standalone**

Run: `uv run scripts/version_guard.py --help`
Expected: Help text showing `check` and `hook` subcommands

---

## Phase 2 Items (NOT in this plan -- future work)

These were explicitly deferred by the CTO:

1. Pre-release version support (`v1.0.0-alpha.1`)
2. Monorepo per-package versioning
3. Shared Python module with release-prep skill
4. CalVer detection and fallback
5. CHANGELOG entry content verification (checking that the version number appears in CHANGELOG.md, not just that the file is staged)
6. Integration with release-prep skill (make release-prep invoke version-guard check)
7. Auto-detection of conventional commits from commit history patterns (the `>80%` heuristic)
