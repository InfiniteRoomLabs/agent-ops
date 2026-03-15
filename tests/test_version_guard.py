"""Tests for version-guard.py."""

import json
import subprocess as sp
from pathlib import Path

import semver

from version_guard import ManifestSpec


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
    assert config.manifests == []
    assert config.changelog == "CHANGELOG.md"
    assert config.tag_prefix == "v"


def test_load_config_detects_commitlint(git_repo: Path) -> None:
    """Presence of commitlint config upgrades strategy to conventional."""
    from version_guard import load_config

    (git_repo / ".commitlintrc.json").write_text("{}")
    config = load_config(git_repo)
    assert config.strategy == "conventional"


def test_detect_package_json(git_repo: Path) -> None:
    from version_guard import detect_manifests
    (git_repo / "package.json").write_text('{"version": "1.2.3"}')
    manifests = detect_manifests(git_repo)
    assert len(manifests) == 1
    assert manifests[0].path == "package.json"
    assert manifests[0].field == "version"

def test_detect_pyproject_toml(git_repo: Path) -> None:
    from version_guard import detect_manifests
    (git_repo / "pyproject.toml").write_text('[project]\nname = "foo"\nversion = "0.1.0"\n')
    manifests = detect_manifests(git_repo)
    assert len(manifests) == 1
    assert manifests[0].path == "pyproject.toml"

def test_detect_plugin_json(git_repo: Path) -> None:
    from version_guard import detect_manifests
    plugin_dir = git_repo / ".claude-plugin"
    plugin_dir.mkdir()
    (plugin_dir / "plugin.json").write_text('{"version": "1.0.0"}')
    manifests = detect_manifests(git_repo)
    assert len(manifests) == 1
    assert manifests[0].path == ".claude-plugin/plugin.json"

def test_detect_no_manifests(git_repo: Path) -> None:
    from version_guard import detect_manifests
    manifests = detect_manifests(git_repo)
    assert manifests == []

def test_detect_multiple_manifests(git_repo: Path) -> None:
    from version_guard import detect_manifests
    (git_repo / "package.json").write_text('{"version": "1.0.0"}')
    (git_repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "1.0.0"\n')
    manifests = detect_manifests(git_repo)
    assert len(manifests) == 2


def test_read_version_from_json(git_repo: Path) -> None:
    from version_guard import read_manifest_version
    (git_repo / "package.json").write_text('{"version": "2.1.0"}')
    version = read_manifest_version(git_repo, ManifestSpec(path="package.json", field="version"))
    assert version == "2.1.0"

def test_read_version_from_toml(git_repo: Path) -> None:
    from version_guard import read_manifest_version
    (git_repo / "pyproject.toml").write_text('[project]\nname = "foo"\nversion = "3.0.1"\n')
    version = read_manifest_version(git_repo, ManifestSpec(path="pyproject.toml", field="project.version"))
    assert version == "3.0.1"

def test_read_version_missing_file(git_repo: Path) -> None:
    from version_guard import read_manifest_version
    version = read_manifest_version(git_repo, ManifestSpec(path="nope.json", field="version"))
    assert version is None

def test_read_version_missing_field(git_repo: Path) -> None:
    from version_guard import read_manifest_version
    (git_repo / "package.json").write_text('{"name": "foo"}')
    version = read_manifest_version(git_repo, ManifestSpec(path="package.json", field="version"))
    assert version is None

def test_manifest_consistency_all_match(git_repo: Path) -> None:
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


# -- Task 5: Git tag version detection --


def test_get_latest_tag_version(tagged_repo: Path) -> None:
    from version_guard import get_latest_tag_version
    ver = get_latest_tag_version("v")
    assert ver == semver.Version.parse("1.0.0")


def test_get_latest_tag_version_no_tags(git_repo: Path) -> None:
    from version_guard import get_latest_tag_version
    ver = get_latest_tag_version("v")
    assert ver is None


def test_get_latest_tag_version_multiple(tagged_repo: Path) -> None:
    from version_guard import get_latest_tag_version
    (tagged_repo / "a.txt").write_text("a")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "feat: add a"], check=True, capture_output=True)
    sp.run(["git", "tag", "-a", "v1.1.0", "-m", "v1.1.0"], check=True, capture_output=True)
    ver = get_latest_tag_version("v")
    assert ver == semver.Version.parse("1.1.0")


# -- Task 6: Conventional commits parser --


def test_compute_bump_from_fix(tagged_repo: Path) -> None:
    from version_guard import compute_next_version
    (tagged_repo / "b.txt").write_text("b")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "fix: correct typo"], check=True, capture_output=True)
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.0.1")


def test_compute_bump_from_feat(tagged_repo: Path) -> None:
    from version_guard import compute_next_version
    (tagged_repo / "c.txt").write_text("c")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "feat: add widget"], check=True, capture_output=True)
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.1.0")


def test_compute_bump_from_breaking_bang(tagged_repo: Path) -> None:
    from version_guard import compute_next_version
    (tagged_repo / "d.txt").write_text("d")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "feat!: redesign API"], check=True, capture_output=True)
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("2.0.0")


def test_compute_bump_from_breaking_footer(tagged_repo: Path) -> None:
    from version_guard import compute_next_version
    (tagged_repo / "e.txt").write_text("e")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "feat: new thing\n\nBREAKING CHANGE: removed old API"], check=True, capture_output=True)
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("2.0.0")


def test_compute_bump_highest_wins(tagged_repo: Path) -> None:
    from version_guard import compute_next_version
    for name, msg in [("f.txt", "fix: a"), ("g.txt", "feat: b"), ("h.txt", "fix: c")]:
        (tagged_repo / name).write_text(name)
        sp.run(["git", "add", "."], check=True, capture_output=True)
        sp.run(["git", "commit", "-m", msg], check=True, capture_output=True)
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.1.0")


def test_compute_bump_no_bumping_commits(tagged_repo: Path) -> None:
    from version_guard import compute_next_version
    (tagged_repo / "i.txt").write_text("i")
    sp.run(["git", "add", "."], check=True, capture_output=True)
    sp.run(["git", "commit", "-m", "chore: update readme"], check=True, capture_output=True)
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.0.0")


def test_compute_bump_no_commits_since_tag(tagged_repo: Path) -> None:
    from version_guard import compute_next_version
    nxt = compute_next_version(semver.Version.parse("1.0.0"), "v")
    assert nxt == semver.Version.parse("1.0.0")


# -- Task 7: Core evaluate() function --


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

    # Need a manifest so we don't exit early at "no manifests found"
    (git_repo / "package.json").write_text('{"version": "1.0.0"}')
    sp.run(["git", "add", "."], check=True, capture_output=True)

    config = VersionGuardConfig(strategy="conventional")
    result = evaluate(
        config=config,
        project_dir=git_repo,
        commit_message="release: v1.0.0",
        is_tag=False,
    )
    assert result.allowed is True
    assert "no version tags" in result.message.lower()


# -- Task 8: CLI commands (check + hook) --


def test_check_command_passes(repo_with_manifest: Path) -> None:
    """check command exits 0 when manifests are consistent and version > tag."""
    from typer.testing import CliRunner

    from version_guard import app

    # Bump manifest ahead of the tag so Tier 1 doesn't block
    (repo_with_manifest / "package.json").write_text('{"version": "1.1.0"}')
    sp.run(["git", "add", "."], check=True, capture_output=True)

    runner = CliRunner()
    result = runner.invoke(app, ["check", "--project-dir", str(repo_with_manifest)])
    assert result.exit_code == 0


def test_hook_ignores_non_commit(git_repo: Path) -> None:
    """Hook exits 0 for non-commit Bash commands."""
    from typer.testing import CliRunner

    from version_guard import app

    runner = CliRunner()
    result = runner.invoke(app, ["hook"], input='{"tool_name": "Bash", "tool_input": {"command": "ls -la"}}')
    assert result.exit_code == 0


def test_hook_blocks_combined_add_commit(git_repo: Path) -> None:
    """Hook blocks combined git add + git commit."""
    from typer.testing import CliRunner

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
    from typer.testing import CliRunner

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
    from typer.testing import CliRunner

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
    from typer.testing import CliRunner

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
    assert result.exit_code == 2
