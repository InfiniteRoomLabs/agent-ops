"""Encoding artifact detection for UTF-8 validation."""
from __future__ import annotations

ENCODING_ARTIFACTS: frozenset[str] = frozenset({
    "\u201c",  # LEFT DOUBLE QUOTATION MARK
    "\u201d",  # RIGHT DOUBLE QUOTATION MARK
    "\u2018",  # LEFT SINGLE QUOTATION MARK
    "\u2019",  # RIGHT SINGLE QUOTATION MARK
    "\u2013",  # EN DASH
    "\u2014",  # EM DASH
    "\u2026",  # HORIZONTAL ELLIPSIS
    "\u2022",  # BULLET
    "\u00a0",  # NO-BREAK SPACE
    "\u2192",  # RIGHTWARDS ARROW
})


def find_encoding_artifacts(content: str) -> set[str]:
    """Return the set of encoding artifact characters found in content."""
    return {c for c in ENCODING_ARTIFACTS if c in content}


def format_artifact_codepoints(found: set[str]) -> str:
    """Render found artifact characters as a sorted 'U+201C, U+2014' list."""
    return ", ".join(f"U+{ord(c):04X}" for c in sorted(found))
