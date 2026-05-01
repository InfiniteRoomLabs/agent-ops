"""Tests for tools/version_bump.py."""

from __future__ import annotations

import importlib.util
import json
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest

_TOOLS = Path(__file__).resolve().parent.parent / "tools"
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))


def _load_module(monkeypatch: pytest.MonkeyPatch, repo: Path) -> Any:
    spec = importlib.util.spec_from_file_location(
        "version_bump", _TOOLS / "version_bump.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # Repoint module-level constants at the fake repo so each test is hermetic.
    monkeypatch.setattr(mod, "REPO_ROOT", repo)
    monkeypatch.setattr(mod, "PYPROJECT", repo / "pyproject.toml")
    monkeypatch.setattr(mod, "PLUGIN_JSON", repo / ".claude-plugin" / "plugin.json")
    monkeypatch.setattr(
        mod, "MARKETPLACE_JSON", repo / ".claude-plugin" / "marketplace.json"
    )
    return mod


@pytest.fixture()
def fake_repo(tmp_path: Path) -> Path:
    (tmp_path / ".claude-plugin").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "x"\nversion = "1.0.0"\n', encoding="utf-8"
    )
    (tmp_path / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "agency", "version": "1.0.0"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (tmp_path / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps(
            {"plugins": [{"name": "agency", "version": "0.1.0"}]}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    return tmp_path


# -- _parse_bump / _apply_bump ----------------------------------------------


def test_parse_bump_levels(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    vb = _load_module(monkeypatch, tmp_path)
    assert vb._parse_bump("major") == ("level", "major")
    assert vb._parse_bump("minor") == ("level", "minor")
    assert vb._parse_bump("patch") == ("level", "patch")


def test_parse_bump_set_value(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vb = _load_module(monkeypatch, tmp_path)
    assert vb._parse_bump("set:2.5.7") == ("set", "2.5.7")


def test_parse_bump_rejects_garbage(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    vb = _load_module(monkeypatch, tmp_path)
    import typer

    with pytest.raises(typer.BadParameter):
        vb._parse_bump("bogus")
    with pytest.raises(ValueError):
        # set: with a non-semver value should raise from semver.parse
        vb._parse_bump("set:not-a-version")


@pytest.mark.parametrize(
    "current,spec,expected",
    [
        ("1.2.3", "major", "2.0.0"),
        ("1.2.3", "minor", "1.3.0"),
        ("1.2.3", "patch", "1.2.4"),
        ("1.2.3", "set:9.9.9", "9.9.9"),
        ("0.0.1", "major", "1.0.0"),
    ],
)
def test_apply_bump(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    current: str,
    spec: str,
    expected: str,
) -> None:
    vb = _load_module(monkeypatch, tmp_path)
    assert vb._apply_bump(current, spec) == expected


# -- file I/O ----------------------------------------------------------------


def test_pyproject_round_trip(
    monkeypatch: pytest.MonkeyPatch, fake_repo: Path
) -> None:
    vb = _load_module(monkeypatch, fake_repo)
    assert vb._read_pyproject_version() == "1.0.0"
    vb._write_pyproject_version("2.5.0")
    assert vb._read_pyproject_version() == "2.5.0"
    # File still parses as TOML and other content is intact.
    data = tomllib.loads((fake_repo / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == "x"


def test_plugin_json_round_trip(
    monkeypatch: pytest.MonkeyPatch, fake_repo: Path
) -> None:
    vb = _load_module(monkeypatch, fake_repo)
    assert vb._read_plugin_version() == "1.0.0"
    vb._write_plugin_version("3.0.0")
    assert vb._read_plugin_version() == "3.0.0"
    data = json.loads(
        (fake_repo / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    assert data["name"] == "agency"


def test_marketplace_round_trip(
    monkeypatch: pytest.MonkeyPatch, fake_repo: Path
) -> None:
    vb = _load_module(monkeypatch, fake_repo)
    assert vb._read_marketplace_version("agency") == "0.1.0"
    vb._write_marketplace_version("0.2.0", "agency")
    assert vb._read_marketplace_version("agency") == "0.2.0"


def test_marketplace_unknown_plugin_raises(
    monkeypatch: pytest.MonkeyPatch, fake_repo: Path
) -> None:
    vb = _load_module(monkeypatch, fake_repo)
    import typer

    with pytest.raises(typer.Exit):
        vb._read_marketplace_version("does-not-exist")


# -- end-to-end via the typer Command (no subprocess) ------------------------


def _run(mod: Any, *args: str) -> int:
    """Invoke the typer app the same way `uv run version_bump.py ...` would."""
    from typer.testing import CliRunner

    runner = CliRunner()
    result = runner.invoke(mod.app, list(args))
    return result.exit_code


def test_e2e_all_minor_no_lock(
    monkeypatch: pytest.MonkeyPatch, fake_repo: Path
) -> None:
    vb = _load_module(monkeypatch, fake_repo)
    code = _run(vb, "--all", "minor", "--no-lock")
    assert code == 0
    assert vb._read_plugin_version() == "1.1.0"
    assert vb._read_pyproject_version() == "1.1.0"
    assert vb._read_marketplace_version("agency") == "0.2.0"


def test_e2e_marketplace_only_does_not_touch_others(
    monkeypatch: pytest.MonkeyPatch, fake_repo: Path
) -> None:
    vb = _load_module(monkeypatch, fake_repo)
    code = _run(vb, "--marketplace", "patch", "--no-lock")
    assert code == 0
    assert vb._read_plugin_version() == "1.0.0"
    assert vb._read_pyproject_version() == "1.0.0"
    assert vb._read_marketplace_version("agency") == "0.1.1"


def test_e2e_dry_run_writes_nothing(
    monkeypatch: pytest.MonkeyPatch, fake_repo: Path
) -> None:
    vb = _load_module(monkeypatch, fake_repo)
    code = _run(vb, "--all", "major", "--dry-run", "--no-lock")
    assert code == 0
    assert vb._read_plugin_version() == "1.0.0"
    assert vb._read_pyproject_version() == "1.0.0"
    assert vb._read_marketplace_version("agency") == "0.1.0"


def test_e2e_no_args_exits_2(
    monkeypatch: pytest.MonkeyPatch, fake_repo: Path
) -> None:
    vb = _load_module(monkeypatch, fake_repo)
    code = _run(vb, "--no-lock")
    assert code == 2
