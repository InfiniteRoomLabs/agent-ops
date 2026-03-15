"""Tests for version-guard.py."""

from pathlib import Path

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
