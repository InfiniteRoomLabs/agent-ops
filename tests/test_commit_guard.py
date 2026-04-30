"""Tests for scripts/commit_guard.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import commit_guard  # noqa: E402


# ---------------------------------------------------------------------------
# packages/ heuristic -- the .NET vs JS-monorepo false positive that motivated
# this fix. Repro: staging packages/core/src/sync/state.ts in a pnpm workspace
# was being blocked as ".NET: packages/" even though there is no .NET in sight.
# ---------------------------------------------------------------------------


def _make_pnpm_monorepo(root: Path) -> None:
    """JS workspace using pnpm with packages/ as the source root."""
    (root / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")
    (root / "package.json").write_text('{"name": "demo", "private": true}\n')
    pkg = root / "packages" / "core" / "src" / "sync"
    pkg.mkdir(parents=True)
    (pkg / "state.ts").write_text("export const x = 1;\n")


def _make_npm_workspaces_monorepo(root: Path) -> None:
    """JS workspace using npm/yarn 'workspaces' field in package.json."""
    (root / "package.json").write_text(
        json.dumps({"name": "demo", "private": True, "workspaces": ["packages/*"]})
        + "\n"
    )
    pkg = root / "packages" / "ui" / "src"
    pkg.mkdir(parents=True)
    (pkg / "index.tsx").write_text("export {};\n")


def _make_dotnet_repo(root: Path) -> None:
    """Legacy .NET project with sibling .csproj/.sln plus a packages/ tree."""
    (root / "App.sln").write_text("Microsoft Visual Studio Solution File\n")
    (root / "MyLib.csproj").write_text(
        '<Project Sdk="Microsoft.NET.Sdk"></Project>\n'
    )
    pkg = root / "packages" / "Newtonsoft.Json.13.0.1" / "lib"
    pkg.mkdir(parents=True)
    (pkg / "Newtonsoft.Json.dll").write_text("binary-stub\n")


def test_packages_dir_allowed_in_pnpm_workspace(git_repo: Path) -> None:
    """JS pnpm monorepo: packages/foo/src/index.ts must NOT be flagged."""
    _make_pnpm_monorepo(git_repo)
    staged = ["packages/core/src/sync/state.ts"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert violations == [], (
        "pnpm workspace 'packages/' was flagged as .NET; predicate should "
        "have skipped it. Got: " + repr(violations)
    )


def test_packages_dir_allowed_in_npm_workspaces(git_repo: Path) -> None:
    """JS npm/yarn workspaces in package.json: packages/ is source, not artifact."""
    _make_npm_workspaces_monorepo(git_repo)
    staged = ["packages/ui/src/index.tsx"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert violations == []


def test_packages_dir_flagged_in_dotnet_repo(git_repo: Path) -> None:
    """Real .NET repo: packages/ IS the legacy NuGet artifact dir, still flag it."""
    _make_dotnet_repo(git_repo)
    staged = ["packages/Newtonsoft.Json.13.0.1/lib/Newtonsoft.Json.dll"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert len(violations) == 1
    fp, pat = violations[0]
    assert fp == staged[0]
    assert pat.pattern == "packages/"
    assert pat.ecosystem == ".NET"


def test_packages_dir_not_flagged_when_no_signals(git_repo: Path) -> None:
    """Bare repo with no manifests: don't false-positive on packages/."""
    pkg = git_repo / "packages" / "anything"
    pkg.mkdir(parents=True)
    (pkg / "file.txt").write_text("hi\n")
    staged = ["packages/anything/file.txt"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert violations == []


def test_packages_dir_flagged_on_legacy_packages_config_csproj(git_repo: Path) -> None:
    """Old-style .NET project: detect <packages> reference inside a .csproj."""
    (git_repo / "Legacy.csproj").write_text(
        "<Project>\n"
        "  <ItemGroup>\n"
        '    <Reference Include="System.Web" />\n'
        "  </ItemGroup>\n"
        "  <packages>\n"
        '    <package id="EntityFramework" version="6.0.0" />\n'
        "  </packages>\n"
        "</Project>\n"
    )
    # Stage the csproj so git ls-files sees it
    import subprocess

    subprocess.run(
        ["git", "-C", str(git_repo), "add", "Legacy.csproj"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(git_repo), "commit", "-m", "add csproj"],
        check=True,
        capture_output=True,
    )
    pkg = git_repo / "packages" / "EntityFramework.6.0.0"
    pkg.mkdir(parents=True)
    (pkg / "EntityFramework.dll").write_text("stub\n")
    staged = ["packages/EntityFramework.6.0.0/EntityFramework.dll"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert len(violations) == 1
    assert violations[0][1].pattern == "packages/"


# ---------------------------------------------------------------------------
# Other .NET artifact dirs must still be unconditionally blocked.
# ---------------------------------------------------------------------------


def test_bin_dir_flagged_regardless_of_repo_type(git_repo: Path) -> None:
    """bin/ remains flagged even in a JS workspace -- it's still an artifact dir."""
    _make_pnpm_monorepo(git_repo)
    staged = ["bin/Debug/net8.0/MyApp.dll"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert any(pat.pattern == "bin/" for _, pat in violations)


def test_obj_dir_flagged_regardless_of_repo_type(git_repo: Path) -> None:
    """obj/ remains flagged unconditionally."""
    _make_pnpm_monorepo(git_repo)
    staged = ["obj/Debug/project.assets.json"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert any(pat.pattern == "obj/" for _, pat in violations)


# ---------------------------------------------------------------------------
# Sanity: existing matchers still work.
# ---------------------------------------------------------------------------


def test_node_modules_still_flagged(git_repo: Path) -> None:
    staged = ["node_modules/foo/index.js"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert any(pat.pattern == "node_modules/" for _, pat in violations)


def test_python_pycache_still_flagged(git_repo: Path) -> None:
    staged = ["src/foo/__pycache__/bar.cpython-312.pyc"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert any(pat.pattern == "__pycache__/" for _, pat in violations)


def test_clean_file_passes(git_repo: Path) -> None:
    _make_pnpm_monorepo(git_repo)
    staged = ["packages/core/src/index.ts", "README.md", "src/main.py"]
    violations = commit_guard.find_violations(staged, root=git_repo)
    assert violations == []


# ---------------------------------------------------------------------------
# Detector unit tests
# ---------------------------------------------------------------------------


def test_has_dotnet_evidence_detects_csproj_at_root(git_repo: Path) -> None:
    (git_repo / "App.csproj").write_text("<Project></Project>\n")
    assert commit_guard._has_dotnet_evidence(git_repo) is True


def test_has_dotnet_evidence_returns_false_for_clean_repo(git_repo: Path) -> None:
    assert commit_guard._has_dotnet_evidence(git_repo) is False


def test_has_js_workspace_evidence_detects_pnpm(git_repo: Path) -> None:
    (git_repo / "pnpm-workspace.yaml").write_text("packages:\n  - 'packages/*'\n")
    assert commit_guard._has_js_workspace_evidence(git_repo) is True


def test_has_js_workspace_evidence_detects_workspaces_field(git_repo: Path) -> None:
    (git_repo / "package.json").write_text(
        json.dumps({"workspaces": ["packages/*"]}) + "\n"
    )
    assert commit_guard._has_js_workspace_evidence(git_repo) is True


def test_has_js_workspace_evidence_ignores_plain_package_json(git_repo: Path) -> None:
    """A package.json without 'workspaces' is just a single project, not a monorepo."""
    (git_repo / "package.json").write_text(
        json.dumps({"name": "x", "version": "1.0.0"}) + "\n"
    )
    assert commit_guard._has_js_workspace_evidence(git_repo) is False


@pytest.mark.parametrize(
    "marker,content",
    [
        ("lerna.json", "{}"),
        ("nx.json", "{}"),
        ("turbo.json", "{}"),
    ],
)
def test_has_js_workspace_evidence_detects_other_monorepo_tools(
    git_repo: Path, marker: str, content: str
) -> None:
    (git_repo / marker).write_text(content + "\n")
    assert commit_guard._has_js_workspace_evidence(git_repo) is True
