"""Tests for version-guard.py."""

from pathlib import Path


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
