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
