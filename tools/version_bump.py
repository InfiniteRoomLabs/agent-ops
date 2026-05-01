# /// script
# dependencies = ["typer>=0.15", "semver>=3"]
# ///
"""Bump versions across pyproject.toml, plugin.json, and marketplace.json.

This script lives in `tools/` because it is repo-internal -- it is not part
of any plugin's distribution surface.

Examples:
  uv run tools/version_bump.py --all minor
  uv run tools/version_bump.py --plugin minor --pyproject minor
  uv run tools/version_bump.py --marketplace patch
  uv run tools/version_bump.py --plugin minor --pyproject minor --marketplace patch
  uv run tools/version_bump.py --plugin set:1.13.0
  uv run tools/version_bump.py --dry-run --all minor

Notes:
- pyproject.toml and plugin.json track the SAME version (the plugin version).
  If you bump one and not the other, the version-guard hook will block your
  next commit.
- marketplace.json carries an INDEPENDENT version on the plugin entry, used
  by the marketplace catalog. It is not synced to plugin.json.
- This script does NOT touch CHANGELOG.md. After bumping, write a
  `## [agency-<new>] - YYYY-MM-DD` section by hand.
- This script does NOT git add/commit. Stage and commit yourself.
- pyproject changes are reflected in uv.lock by running `uv lock` at the end
  unless --no-lock is passed.
"""

from __future__ import annotations

import json
import re
import subprocess
import tomllib
from pathlib import Path
from typing import Annotated, Optional

import semver
import typer

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
PLUGIN_JSON = REPO_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_JSON = REPO_ROOT / ".claude-plugin" / "marketplace.json"

LEVELS = ("major", "minor", "patch")

app = typer.Typer(
    help="Bump versions across pyproject.toml, plugin.json, and marketplace.json.",
    no_args_is_help=True,
)


# -- bump-level parsing ------------------------------------------------------


def _parse_bump(spec: str) -> tuple[str, str | None]:
    """Return ('level', None) or ('set', '1.2.3'). Raises on bad input."""
    if spec in LEVELS:
        return ("level", spec)
    if spec.startswith("set:"):
        candidate = spec[len("set:"):]
        # Validate it parses as semver before accepting.
        semver.Version.parse(candidate)
        return ("set", candidate)
    raise typer.BadParameter(
        f"bump must be one of {LEVELS} or 'set:X.Y.Z'; got {spec!r}"
    )


def _apply_bump(current: str, spec: str) -> str:
    kind, value = _parse_bump(spec)
    if kind == "set":
        assert value is not None
        return value
    cur = semver.Version.parse(current)
    bumped: semver.Version
    if value == "major":
        bumped = cur.bump_major()
    elif value == "minor":
        bumped = cur.bump_minor()
    elif value == "patch":
        bumped = cur.bump_patch()
    else:  # pragma: no cover -- _parse_bump already validated
        raise RuntimeError(f"unknown level: {value}")
    return str(bumped)


# -- file readers / writers --------------------------------------------------


def _fail(msg: str, code: int = 1) -> typer.Exit:
    typer.echo(msg, err=True)
    return typer.Exit(code)


def _read_pyproject_version() -> str:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    v = data.get("project", {}).get("version")
    if not v:
        raise _fail(f"no [project].version in {PYPROJECT}")
    return v


def _write_pyproject_version(new: str) -> None:
    text = PYPROJECT.read_text(encoding="utf-8")
    # Match the first `version = "X.Y.Z"` under [project]. Naive but safe
    # for our pyproject because we only set version once.
    pattern = re.compile(r'^(version\s*=\s*")[^"]+(")', re.MULTILINE)
    new_text, count = pattern.subn(rf'\g<1>{new}\g<2>', text, count=1)
    if count != 1:
        raise _fail(f"failed to rewrite version in {PYPROJECT}")
    PYPROJECT.write_text(new_text, encoding="utf-8")


def _read_plugin_version() -> str:
    return json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))["version"]


def _write_plugin_version(new: str) -> None:
    data = json.loads(PLUGIN_JSON.read_text(encoding="utf-8"))
    data["version"] = new
    PLUGIN_JSON.write_text(
        json.dumps(data, indent=2) + "\n", encoding="utf-8"
    )


def _read_marketplace_version(plugin_name: str = "agency") -> str:
    data = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    for entry in data.get("plugins", []):
        if entry.get("name") == plugin_name:
            return entry["version"]
    raise _fail(f"plugin '{plugin_name}' not found in {MARKETPLACE_JSON}")


def _write_marketplace_version(new: str, plugin_name: str = "agency") -> None:
    data = json.loads(MARKETPLACE_JSON.read_text(encoding="utf-8"))
    for entry in data.get("plugins", []):
        if entry.get("name") == plugin_name:
            entry["version"] = new
            MARKETPLACE_JSON.write_text(
                json.dumps(data, indent=2) + "\n", encoding="utf-8"
            )
            return
    raise _fail(f"plugin '{plugin_name}' not found in {MARKETPLACE_JSON}")


# -- main command ------------------------------------------------------------


@app.command()
def bump(
    all_: Annotated[
        Optional[str],
        typer.Option(
            "--all",
            help="Apply this bump to plugin + pyproject + marketplace. Per-file flags override.",
        ),
    ] = None,
    plugin: Annotated[
        Optional[str],
        typer.Option(
            "--plugin",
            help="Bump plugin.json. major|minor|patch or set:X.Y.Z.",
        ),
    ] = None,
    pyproject: Annotated[
        Optional[str],
        typer.Option(
            "--pyproject",
            help="Bump pyproject.toml. Should match --plugin or version-guard will block.",
        ),
    ] = None,
    marketplace: Annotated[
        Optional[str],
        typer.Option(
            "--marketplace",
            help="Bump the agency entry in marketplace.json. Independent of plugin/pyproject.",
        ),
    ] = None,
    plugin_name: Annotated[
        str,
        typer.Option(
            "--plugin-name",
            help="Marketplace plugin entry name to update.",
        ),
    ] = "agency",
    no_lock: Annotated[
        bool,
        typer.Option(
            "--no-lock",
            help="Skip 'uv lock' after editing pyproject.toml.",
        ),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run",
            help="Print planned changes; write nothing.",
        ),
    ] = False,
) -> None:
    """Bump versions across the three manifests this repo cares about."""
    plugin = plugin or all_
    pyproject = pyproject or all_
    marketplace = marketplace or all_

    if not any([plugin, pyproject, marketplace]):
        typer.echo(
            "nothing to do -- pass --all, --plugin, --pyproject, or --marketplace",
            err=True,
        )
        raise typer.Exit(2)

    plan: list[tuple[str, str, str]] = []  # (label, old, new)

    if plugin:
        old = _read_plugin_version()
        plan.append(("plugin.json", old, _apply_bump(old, plugin)))
    if pyproject:
        old = _read_pyproject_version()
        plan.append(("pyproject.toml", old, _apply_bump(old, pyproject)))
    if marketplace:
        old = _read_marketplace_version(plugin_name)
        plan.append(("marketplace.json", old, _apply_bump(old, marketplace)))

    width = max(len(label) for label, _, _ in plan)
    for label, old, new in plan:
        marker = " (DRY)" if dry_run else ""
        typer.echo(f"  {label:<{width}}  {old} -> {new}{marker}")

    # Sanity-warn if plugin and pyproject diverge.
    plugin_new = next((n for l, _, n in plan if l == "plugin.json"), None)
    pyproject_new = next((n for l, _, n in plan if l == "pyproject.toml"), None)
    if plugin_new and pyproject_new and plugin_new != pyproject_new:
        typer.echo(
            "WARNING: plugin.json and pyproject.toml will disagree -- the "
            "version-guard hook will block your next commit.",
            err=True,
        )
    elif (plugin_new or pyproject_new) and not (plugin_new and pyproject_new):
        # Only one of the synced pair is being bumped.
        other = "pyproject.toml" if plugin_new else "plugin.json"
        typer.echo(
            f"WARNING: only one of (plugin.json, pyproject.toml) is being "
            f"bumped -- {other} will be left at its current version and "
            f"version-guard will block your next commit.",
            err=True,
        )

    if dry_run:
        typer.echo("dry-run: no files written.", err=True)
        raise typer.Exit(0)

    for label, _, new in plan:
        if label == "plugin.json":
            _write_plugin_version(new)
        elif label == "pyproject.toml":
            _write_pyproject_version(new)
        elif label == "marketplace.json":
            _write_marketplace_version(new, plugin_name)

    if pyproject and not no_lock:
        typer.echo("running uv lock to refresh uv.lock...", err=True)
        result = subprocess.run(
            ["uv", "lock"], cwd=REPO_ROOT, capture_output=True, text=True
        )
        if result.returncode != 0:
            typer.echo(result.stderr, err=True)
            raise typer.Exit(result.returncode)

    typer.echo("done. now edit CHANGELOG.md, stage, and commit.", err=True)


if __name__ == "__main__":
    app()
