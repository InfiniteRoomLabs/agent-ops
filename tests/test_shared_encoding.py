"""Tests for _shared.encoding module."""
from __future__ import annotations

from _shared.encoding import ENCODING_ARTIFACTS, find_encoding_artifacts


def test_encoding_artifacts_is_frozenset() -> None:
    """ENCODING_ARTIFACTS is a frozenset."""
    assert isinstance(ENCODING_ARTIFACTS, frozenset)


def test_find_artifacts_detects_smart_quotes() -> None:
    """Detects left double quotation mark (U+201C)."""
    content = 'She said \u201chello\u201d'
    found = find_encoding_artifacts(content)
    assert "\u201c" in found
    assert "\u201d" in found


def test_find_artifacts_clean_content() -> None:
    """ASCII-only content returns an empty set."""
    assert find_encoding_artifacts("Hello, world!") == set()
