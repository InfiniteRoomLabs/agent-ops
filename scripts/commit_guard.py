# /// script
# dependencies = ["pydantic>=2", "typer>=0.15"]
# ///
"""Guard against committing files that should be gitignored.

Usage:
  Human:  uv run commit_guard.py check
  Hook:   uv run commit_guard.py pre   (reads PreToolUse JSON from stdin)
          uv run commit_guard.py post  (reads PostToolUse JSON from stdin)
  List:   uv run commit_guard.py rules (print the active patterns table)
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path
from typing import Callable, Optional

import typer
from pydantic import BaseModel

app = typer.Typer(
    help="Guard against committing files that should be gitignored.",
    no_args_is_help=True,
)

# ---------------------------------------------------------------------------
# Patterns table -- edit this to add ignored-path checks
# ---------------------------------------------------------------------------


@dataclass
class IgnoredPattern:
    """A single ignored-path pattern.

    pattern:    fnmatch glob. Trailing '/' means directory (match any path
                component). No trailing '/' means match the basename.
    ecosystem:  Human-readable label for output grouping.
    message:    Optional custom message. Falls back to generic if empty.
    requires:   Optional predicate (root: Path -> bool). When set, the pattern
                only flags violations if the predicate returns True for the
                current repo root. Used to gate ambiguous patterns like
                'packages/' on real ecosystem evidence.
    """

    pattern: str
    ecosystem: str
    message: str = ""
    requires: Optional[Callable[[Path], bool]] = field(default=None, repr=False, compare=False)


# ---------------------------------------------------------------------------
# Repo-context detectors -- distinguish ambiguous directory names by scanning
# tracked + working files for ecosystem markers.
# ---------------------------------------------------------------------------


_DOTNET_GLOBS = (
    "*.csproj",
    "*.fsproj",
    "*.vbproj",
    "*.sln",
    "global.json",
    "NuGet.Config",
    "nuget.config",
    "packages.config",
    "Directory.Build.props",
    "Directory.Build.targets",
)

_JS_WORKSPACE_FILES = (
    "pnpm-workspace.yaml",
    "pnpm-workspace.yml",
    "lerna.json",
    "nx.json",
    "turbo.json",
    "rush.json",
)


def _git_ls_files(root: Path) -> list[str]:
    """Return tracked files in the repo, or empty list on failure."""
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return []
    if result.returncode != 0:
        return []
    return [line for line in result.stdout.splitlines() if line]


def _has_dotnet_evidence(root: Path) -> bool:
    """True when the repo shows real .NET project signals.

    Looks for project/solution manifests anywhere in the tracked tree, plus
    quick filesystem checks at the root. Catches '<packages>' references in
    .csproj files so legacy package-restore layouts still flag.
    """
    for name in _DOTNET_GLOBS:
        if list(root.glob(name)):
            return True
    tracked = _git_ls_files(root)
    for tracked_path in tracked:
        basename = Path(tracked_path).name
        for glob in _DOTNET_GLOBS:
            if fnmatch(basename, glob):
                return True
    # Inspect any *.csproj for legacy <packages> element which signals
    # the old NuGet packages.config restore layout (uses 'packages/' dir).
    for tracked_path in tracked:
        if tracked_path.endswith(".csproj"):
            try:
                content = (root / tracked_path).read_text(
                    encoding="utf-8", errors="ignore"
                )
            except OSError:
                continue
            if re.search(r"<packages\b", content):
                return True
    return False


def _has_js_workspace_evidence(root: Path) -> bool:
    """True when the repo uses a JS/TS package-based workspace layout."""
    for name in _JS_WORKSPACE_FILES:
        if (root / name).exists():
            return True
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            data = json.loads(pkg_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if isinstance(data, dict) and "workspaces" in data:
            return True
    return False


def _packages_dir_predicate(root: Path) -> bool:
    """Flag 'packages/' only when .NET signals exist and JS workspace doesn't.

    Reasoning: 'packages/' is the canonical workspace source root in
    pnpm/yarn/lerna/nx/turborepo monorepos. It is also the legacy NuGet
    package-restore directory. The basename alone cannot disambiguate. So:

      - JS workspace evidence present  -> never flag (workspace source).
      - .NET evidence present          -> flag (legacy NuGet artifact dir).
      - Neither                        -> do not flag (avoid false positives).
    """
    if _has_js_workspace_evidence(root):
        return False
    return _has_dotnet_evidence(root)


PATTERNS: list[IgnoredPattern] = [
    # Python
    IgnoredPattern("__pycache__/", "Python"),
    IgnoredPattern(".venv/", "Python"),
    IgnoredPattern("venv/", "Python"),
    IgnoredPattern(".eggs/", "Python"),
    IgnoredPattern("*.egg-info/", "Python"),
    # Node
    IgnoredPattern("node_modules/", "Node"),
    IgnoredPattern(".npm/", "Node"),
    IgnoredPattern(".yarn/cache/", "Node"),
    # Ruby (must be before PHP 'vendor/' to avoid shadowing)
    IgnoredPattern("vendor/bundle/", "Ruby"),
    # PHP
    IgnoredPattern("vendor/", "PHP"),
    # Rust
    IgnoredPattern("target/", "Rust"),
    # Java / JVM
    IgnoredPattern(".gradle/", "Java"),
    IgnoredPattern("build/", "Java"),
    # .NET
    IgnoredPattern("bin/", ".NET"),
    IgnoredPattern("obj/", ".NET"),
    IgnoredPattern(
        "packages/",
        ".NET",
        message=(
            "'packages/' looks like a legacy NuGet package-restore directory. "
            "Add 'packages/' to .gitignore and unstage."
        ),
        requires=_packages_dir_predicate,
    ),
    # General
    IgnoredPattern(".env", "General"),
    IgnoredPattern(".DS_Store", "General"),
    IgnoredPattern("Thumbs.db", "General"),
    IgnoredPattern("*.log", "General"),
]

# ---------------------------------------------------------------------------
# Pydantic models for hook JSON payload
# ---------------------------------------------------------------------------


class ToolInput(BaseModel):
    command: str = ""


class HookPayload(BaseModel):
    tool_name: str = ""
    tool_input: ToolInput = ToolInput()


# ---------------------------------------------------------------------------
# Matching logic
# ---------------------------------------------------------------------------


def matches(file_path: str, pattern: str) -> bool:
    """Match a pattern against a staged file path.

    If the pattern ends with '/', strip the slash and check if any path
    component (directory segment) matches via fnmatch. This handles both
    plain names ('vendor/') and globs ('*.egg-info/').

    For multi-segment directory patterns ('vendor/bundle/', '.yarn/cache/'),
    check if the pattern appears as a contiguous path prefix or subsequence.

    Otherwise, fnmatch against the basename.
    """
    if pattern.endswith("/"):
        dir_pattern = pattern.rstrip("/")
        if "/" in dir_pattern:
            normalized = Path(file_path).as_posix()
            return (
                fnmatch(normalized, f"{dir_pattern}/*")
                or fnmatch(normalized, f"*/{dir_pattern}/*")
            )
        parts = Path(file_path).parts
        return any(fnmatch(part, dir_pattern) for part in parts)
    return fnmatch(Path(file_path).name, pattern)


def _repo_root() -> Path:
    """Best-effort repo root. Falls back to cwd when not in a git repo."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return Path.cwd()
    top = result.stdout.strip()
    if result.returncode != 0 or not top:
        return Path.cwd()
    return Path(top)


def find_violations(
    staged_files: list[str],
    root: Optional[Path] = None,
) -> list[tuple[str, IgnoredPattern]]:
    """Return (file_path, matched_pattern) for every staged file that matches.

    Patterns with a `requires` predicate are evaluated once per repo and
    skipped when the predicate returns False.
    """
    if root is None:
        root = _repo_root()
    predicate_cache: dict[int, bool] = {}
    violations: list[tuple[str, IgnoredPattern]] = []
    for filepath in staged_files:
        for pat in PATTERNS:
            if not matches(filepath, pat.pattern):
                continue
            if pat.requires is not None:
                key = id(pat.requires)
                if key not in predicate_cache:
                    try:
                        predicate_cache[key] = bool(pat.requires(root))
                    except Exception:
                        predicate_cache[key] = False
                if not predicate_cache[key]:
                    continue
            violations.append((filepath, pat))
            break  # one match per file is enough
    return violations


def get_staged_files() -> list[str]:
    """Return the list of currently staged file paths."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


@app.command()
def post() -> None:
    """PostToolUse hook: warn if staged files match ignored patterns after git add."""
    try:
        payload = HookPayload.model_validate_json(sys.stdin.read())
    except Exception:
        raise typer.Exit(0)

    if not re.search(r"git\s+add\b", payload.tool_input.command):
        raise typer.Exit(0)

    staged = get_staged_files()
    if not staged:
        raise typer.Exit(0)

    violations = find_violations(staged)
    for filepath, pat in violations:
        msg = pat.message or (
            f"'{filepath}' is a typically gitignored path ({pat.ecosystem}). "
            f"Consider adding '{pat.pattern}' to .gitignore and unstaging."
        )
        typer.echo(f"[commit-guard] WARNING: {msg}", err=True)

    raise typer.Exit(0)


@app.command()
def pre() -> None:
    """PreToolUse hook: block commit if staged files match ignored patterns."""
    try:
        payload = HookPayload.model_validate_json(sys.stdin.read())
    except Exception:
        raise typer.Exit(0)

    if not re.search(r"git\s+commit\b", payload.tool_input.command):
        raise typer.Exit(0)

    staged = get_staged_files()
    if not staged:
        raise typer.Exit(0)

    violations = find_violations(staged)
    if not violations:
        raise typer.Exit(0)

    lines = [f"  - {fp} ({pat.ecosystem}: {pat.pattern})" for fp, pat in violations]
    typer.echo(
        "BLOCKED: Commit includes paths that should be gitignored:\n"
        + "\n".join(lines)
        + "\n\nAdd these patterns to .gitignore and unstage the files before committing.",
        err=True,
    )
    raise typer.Exit(2)


@app.command()
def check() -> None:
    """Check if any currently staged files match ignored patterns."""
    staged = get_staged_files()
    if not staged:
        typer.echo("No files staged.")
        raise typer.Exit(0)

    violations = find_violations(staged)
    if not violations:
        typer.echo(f"All {len(staged)} staged file(s) look clean.")
        raise typer.Exit(0)

    lines = [f"  - {fp} ({pat.ecosystem}: {pat.pattern})" for fp, pat in violations]
    typer.echo(
        "Staged files that should be gitignored:\n"
        + "\n".join(lines)
        + "\n\nAdd these patterns to .gitignore and unstage the files before committing.",
    )
    raise typer.Exit(1)


@app.command()
def rules() -> None:
    """Print the active ignored-path patterns table."""
    current_eco = ""
    for pat in PATTERNS:
        if pat.ecosystem != current_eco:
            if current_eco:
                typer.echo("")
            typer.echo(f"  {pat.ecosystem}:")
            current_eco = pat.ecosystem
        note = f"  ({pat.message})" if pat.message else ""
        typer.echo(f"    {pat.pattern}{note}")


if __name__ == "__main__":
    app()
