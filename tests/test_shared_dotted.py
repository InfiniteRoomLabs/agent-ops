"""Tests for _shared.dotted module."""
from __future__ import annotations

from _shared.dotted import resolve_dotted


def test_resolve_dotted_simple() -> None:
    """Single-level key lookup."""
    assert resolve_dotted({"a": 1}, "a") == 1


def test_resolve_dotted_nested() -> None:
    """Multi-level dotted key traversal."""
    assert resolve_dotted({"a": {"b": 2}}, "a.b") == 2


def test_resolve_dotted_missing() -> None:
    """Missing top-level key returns None."""
    assert resolve_dotted({"a": 1}, "b") is None


def test_resolve_dotted_partial() -> None:
    """Missing nested key returns None."""
    assert resolve_dotted({"a": {"b": 2}}, "a.c") is None
