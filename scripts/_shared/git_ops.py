"""Common git operations."""
from __future__ import annotations

import re
import subprocess

# Heredoc body: <<TAG ... TAG or <<-TAG / <<'TAG' / <<"TAG", up to the closing tag.
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?^[ \t]*\2\b", re.DOTALL | re.MULTILINE)
_SINGLE_Q_RE = re.compile(r"'[^']*'")
_DOUBLE_Q_RE = re.compile(r'"[^"]*"')


def shell_command_skeleton(command: str) -> str:
    """Strip heredoc bodies and quoted spans so command-detection regexes see
    structure, not argument/message text.

    Without this, a commit message that merely mentions "git add" (or an echoed
    JSON payload containing "git commit") false-triggers the guards. Strip order
    matters: heredocs first (their tags can be quoted and their bodies may hold
    unmatched quotes), then single- then double-quoted spans.
    """
    s = _HEREDOC_RE.sub(" ", command)
    s = _SINGLE_Q_RE.sub(" ", s)
    s = _DOUBLE_Q_RE.sub(" ", s)
    return s


def runs_git_command(command: str, subcommand: str) -> bool:
    """True if `command` actually invokes `git <subcommand>` (not inside a
    quoted message/heredoc body)."""
    return re.search(rf"\bgit\s+{subcommand}\b", shell_command_skeleton(command)) is not None


def is_combined_add_commit(command: str) -> bool:
    """True if a single shell command both stages and commits (e.g.
    `git add . && git commit -m ...`).

    The guards inspect the staged index at PreToolUse, BEFORE the command runs,
    so a combined add+commit would have them read a stale (pre-add) index. They
    require the two steps be separate Bash calls so the inspected snapshot is
    final. Note: `git commit -a` / `-am` also stage tracked changes without a
    literal `git add` token -- this detector does not catch that (pre-existing
    gap, out of scope)."""
    skeleton = shell_command_skeleton(command)
    return (
        re.search(r"\bgit\s+add\b", skeleton) is not None
        and re.search(r"\bgit\s+commit\b", skeleton) is not None
    )


def get_current_branch() -> str:
    """Return the current git branch name."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True,
    )
    return result.stdout.strip()


def get_latest_tag(prefix: str = "v") -> str | None:
    """Return the latest tag string matching {prefix}*, or None.

    Sorted by version (git's -v:refname). Returns the full tag string
    including the prefix (e.g., "v1.3.0").
    """
    result = subprocess.run(
        ["git", "tag", "-l", f"{prefix}*", "--sort=-v:refname"],
        capture_output=True, text=True,
    )
    for line in result.stdout.strip().splitlines():
        tag = line.strip()
        if tag:
            return tag
    return None
