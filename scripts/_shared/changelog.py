"""CHANGELOG.md parsing utilities."""
from __future__ import annotations

import re
from pathlib import Path

# Matches ## [agency-1.3.0] or ## [1.3.0] with optional date
CHANGELOG_VERSION_RE = re.compile(r"^##\s+\[(.+?)\]", re.MULTILINE)


def get_latest_changelog_version(
    path: Path,
    *,
    strip_prefix: str = "agency-",
) -> str | None:
    """Parse CHANGELOG.md for the latest version header.

    Skips [Unreleased]. Returns bare version (e.g., "1.3.0") or None.
    """
    if not path.is_file():
        return None

    text = path.read_text(encoding="utf-8")
    for match in CHANGELOG_VERSION_RE.finditer(text):
        raw = match.group(1)
        if raw.lower() == "unreleased":
            continue
        # Strip the prefix (e.g., "agency-") to get bare version
        if strip_prefix and raw.startswith(strip_prefix):
            return raw[len(strip_prefix) :]
        return raw

    return None


def has_content_under_header(
    path: Path,
    version: str,
    *,
    prefix: str = "agency-",
) -> bool:
    """Check if the CHANGELOG section for a version has real content.

    Returns False if section is empty or only has ### category headers.
    Returns True if there are actual bullet points or prose lines.
    """
    if not path.is_file():
        return False

    header_tag = f"{prefix}{version}" if prefix else version
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()

    # Find the ## [prefix+version] header line
    header_pattern = re.compile(rf"^##\s+\[{re.escape(header_tag)}\]")
    in_section = False

    for line in lines:
        if in_section:
            # Stop at the next ## header
            if line.startswith("## "):
                break
            stripped = line.strip()
            # Skip blank lines and ### sub-headers
            if not stripped or stripped.startswith("### "):
                continue
            # Any other content (bullet points, prose) counts
            return True
        elif header_pattern.match(line):
            in_section = True

    return False
