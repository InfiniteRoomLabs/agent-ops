"""Tests for scripts/test-coverage-guard.py."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

_SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _load_module() -> Any:
    """Hyphenated filename can't be imported normally; load via spec."""
    spec = importlib.util.spec_from_file_location(
        "test_coverage_guard", _SCRIPTS / "test-coverage-guard.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tcg = _load_module()


# -- expected_test_path ------------------------------------------------------


def test_expected_test_path_hyphenated() -> None:
    assert tcg.expected_test_path("scripts/foo-bar.py") == "tests/test_foo_bar.py"


def test_expected_test_path_plain() -> None:
    assert tcg.expected_test_path("scripts/x.py") == "tests/test_x.py"


# -- is_in_scope -------------------------------------------------------------


def test_in_scope_top_level_script() -> None:
    assert tcg.is_in_scope("scripts/new_guard.py") is True


def test_in_scope_excludes_shared_subdir() -> None:
    assert tcg.is_in_scope("scripts/_shared/git_ops.py") is False


def test_in_scope_excludes_dunder() -> None:
    assert tcg.is_in_scope("scripts/__init__.py") is False


def test_in_scope_excludes_non_script() -> None:
    assert tcg.is_in_scope("README.md") is False
    assert tcg.is_in_scope("tests/test_x.py") is False


def test_in_scope_respects_exempt(monkeypatch: Any) -> None:
    monkeypatch.setattr(tcg, "EXEMPT", {"constants.py"})
    assert tcg.is_in_scope("scripts/constants.py") is False


# -- evaluate ----------------------------------------------------------------


def test_evaluate_added_script_with_test_allows() -> None:
    allowed, msg = tcg.evaluate(["scripts/foo.py"], present=lambda *_: True)
    assert allowed is True
    assert "matching tests" in msg


def test_evaluate_added_script_missing_test_blocks() -> None:
    allowed, msg = tcg.evaluate(["scripts/foo.py"], present=lambda *_: False)
    assert allowed is False
    assert "BLOCKED" in msg
    assert "tests/test_foo.py" in msg


def test_evaluate_ignores_non_script_additions() -> None:
    # A docs-only addition with no test must not block.
    allowed, _ = tcg.evaluate(["README.md", "docs/guide.md"], present=lambda *_: False)
    assert allowed is True


def test_evaluate_empty_addition_allows() -> None:
    allowed, _ = tcg.evaluate([], present=lambda *_: False)
    assert allowed is True


def test_evaluate_mixed_only_blocks_on_script() -> None:
    # present() returns True only for the script that has a test.
    def present(t: str) -> bool:
        return t == "tests/test_has_test.py"

    allowed, msg = tcg.evaluate(
        ["scripts/has_test.py", "scripts/no_test.py", "README.md"], present=present
    )
    assert allowed is False
    assert "tests/test_no_test.py" in msg
    assert "tests/test_has_test.py" not in msg
