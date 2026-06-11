"""Common git operations."""
from __future__ import annotations

import os
import re
import subprocess
from functools import lru_cache
from pathlib import Path

# Default protected-branch pattern shared by the guards. version_guard's
# per-repo config can override it; changelog-guard uses it as-is.
PROTECTED_BRANCHES_DEFAULT = r"^(main|master|release/.+)$"

# Heredoc body: <<TAG ... TAG or <<-TAG / <<'TAG' / <<"TAG", up to the closing tag.
_HEREDOC_RE = re.compile(r"<<-?\s*(['\"]?)(\w+)\1.*?^[ \t]*\2\b", re.DOTALL | re.MULTILINE)
_SINGLE_Q_RE = re.compile(r"'[^']*'")
_DOUBLE_Q_RE = re.compile(r'"[^"]*"')


@lru_cache(maxsize=8)
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
    final. For `git commit -a` / `-am` / `--all` (which stage tracked changes
    at commit time, same staleness problem) see is_self_staging_commit()."""
    skeleton = shell_command_skeleton(command)
    return (
        re.search(r"\bgit\s+add\b", skeleton) is not None
        and re.search(r"\bgit\s+commit\b", skeleton) is not None
    )


def is_self_staging_commit(command: str) -> bool:
    """True for `git commit -a` / `-am` / `--all` and friends -- commits that
    stage tracked modifications at commit time.

    Same staleness problem as a combined add+commit: the index the guards
    inspected pre-commit is not the index the commit will record. `--amend`
    does NOT match (double-dash, not `--all`)."""
    skeleton = shell_command_skeleton(command)
    m = re.search(r"\bgit\s+commit\b([^;&|]*)", skeleton)
    if not m:
        return False
    segment = m.group(1)
    if re.search(r"(?:^|\s)--all\b", segment):
        return True
    # Short-flag cluster containing 'a' (e.g. -a, -am, -sam). Double-dash
    # options like --amend never match: the char after '-' must be a letter.
    return re.search(r"(?:^|\s)-[a-zA-Z]*a[a-zA-Z]*\b", segment) is not None


def stages_at_commit_time(command: str) -> bool:
    """True when the staged index a PreToolUse guard inspects is NOT the index
    the commit will record: a combined add+commit chain, or a self-staging
    commit (`git commit -a/-am/--all`). This disjunction IS the staleness
    policy -- new staleness forms get added here, not in each guard."""
    return is_combined_add_commit(command) or is_self_staging_commit(command)


STAGING_SEPARATION_MESSAGE = (
    "BLOCKED: Stage and commit in separate Bash calls (and avoid -a/-am).\n"
    "The {guard} guard needs to inspect the final staged files before\n"
    "the commit runs. Run 'git add' first, then a plain 'git commit'."
)


# -- Working-directory resolution ---------------------------------------------

# A `cd <path>` at a command position (start of command, or after && || ; | or
# a newline). The path may be quoted (possibly mixed, e.g. "my dir"/sub).
# Group 1 = the `cd` token (for position validation), group 2 = the path.
_CD_RE = re.compile(
    r"""(?:^|&&|\|\||;|\||\n)\s*(cd)\s+((?:'[^']*'|"[^"]*"|[^\s;&|)])+)"""
)

# `git [global-opts] -C <path>`: -C may follow other global options.
# Group 1 = the `git` token (for position validation), group 2 = the path.
_GIT_C_RE = re.compile(
    r"""\b(git)\s+(?:(?:--[\w-]+(?:=\S+)?|-c\s+\S+)\s+)*-C\s+('[^']*'|"[^"]*"|\S+)"""
)


def _unquote(token: str) -> str:
    token = token.strip()
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return token[1:-1]
    # Mixed quoting ("my dir"/sub): drop any remaining quote chars.
    return token.replace("'", "").replace('"', "")


def _apply_path(base: Path, raw: str) -> Path:
    target = os.path.expandvars(_unquote(raw))
    p = Path(target).expanduser()
    if not p.is_absolute():
        p = base / p
    return Path(os.path.normpath(p))


def effective_cwd(command: str, payload_cwd: str | Path | None = None) -> Path:
    """Resolve the directory a git invocation inside `command` actually runs in.

    Hook processes inherit the session cwd, but the agent's command may hop
    repos first (`cd /other/repo && git commit ...`) or use `git -C <path>`.
    Without this, the guards inspect the WRONG repo's branch/index -- the
    session repo instead of the cd-target (observed live: a cross-repo commit
    falsely blocked because CHANGELOG.md was checked in the session repo).

    Resolution: start from `payload_cwd` (the hook payload's `cwd` field, i.e.
    where the shell command will run), apply each `cd <path>` that appears
    before the first git invocation in order (relative paths chain), then apply
    a `git -C <path>` override if present. Heredoc bodies are stripped first so
    quoted text cannot inject phantom `cd`s. Limitations (accepted): `cd` with
    no argument, `cd -`, and shell variables that are not plain $VAR/${VAR}
    expansions are ignored; a `cd` AFTER the git invocation is not applied only
    when git appears first.
    """
    base = Path(payload_cwd) if payload_cwd else Path.cwd()
    text = _HEREDOC_RE.sub(" ", command)

    # Offset-preserving mask: quoted spans become same-length whitespace.
    # Matches run on `text` (so quoted PATHS stay readable) but each match's
    # command TOKEN is validated against `masked` at the same offset -- a
    # token still visible there is structural, one that got blanked was just
    # text inside a quoted string.
    def _blank(m: re.Match[str]) -> str:
        return " " * len(m.group(0))

    masked = _DOUBLE_Q_RE.sub(_blank, _SINGLE_Q_RE.sub(_blank, text))

    def _structural(token_start: int, token: str) -> bool:
        return masked.startswith(token, token_start)

    git_token = next(
        (m for m in re.finditer(r"\bgit\b", text) if _structural(m.start(), "git")),
        None,
    )
    cutoff = git_token.start() if git_token else len(text)

    cur = base
    for m in _CD_RE.finditer(text):
        if not _structural(m.start(1), "cd"):
            continue  # 'cd' was inside a quoted span
        if m.start(1) >= cutoff:
            break
        raw = m.group(2)
        if _unquote(raw) == "-":
            continue  # previous-dir bounce: unknowable here, keep current
        cur = _apply_path(cur, raw)

    c_match = next(
        (m for m in _GIT_C_RE.finditer(text) if _structural(m.start(1), "git")),
        None,
    )
    if c_match:
        cur = _apply_path(cur, c_match.group(2))
    return cur


def get_repo_root(cwd: str | Path | None = None) -> Path:
    """Repo toplevel for `cwd` (or process cwd). Falls back to `cwd` itself
    when git is unavailable or the directory is not a repo."""
    fallback = Path(cwd) if cwd else Path.cwd()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=fallback,
        )
    except (FileNotFoundError, OSError):
        return fallback
    top = result.stdout.strip()
    if result.returncode != 0 or not top:
        return fallback
    return Path(top)


def resolve_repo_root(command: str, payload_cwd: str | Path | None = None) -> Path:
    """The repo a git invocation in `command` actually targets.

    This is THE entry point for hooks: payload cwd (empty string = absent)
    -> effective_cwd (apply `cd` hops / `git -C`) -> repo toplevel. Without
    it, a cross-repo command (`cd /other/repo && git commit`) gets judged
    against the session repo's branch and index.
    """
    return get_repo_root(effective_cwd(command, payload_cwd or None))


def get_staged_files(cwd: str | Path | None = None) -> list[str]:
    """Currently staged file paths (root-relative), for the repo at `cwd`."""
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=cwd,
    )
    return [line for line in result.stdout.strip().splitlines() if line]


def get_current_branch(cwd: str | Path | None = None) -> str:
    """Return the current git branch name (for the repo at `cwd`, defaulting
    to the process cwd)."""
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        capture_output=True, text=True, cwd=cwd,
    )
    return result.stdout.strip()


def get_latest_tag(prefix: str = "v", cwd: str | Path | None = None) -> str | None:
    """Return the latest tag string matching {prefix}*, or None.

    Sorted by version (git's -v:refname). Returns the full tag string
    including the prefix (e.g., "v1.3.0").
    """
    result = subprocess.run(
        ["git", "tag", "-l", f"{prefix}*", "--sort=-v:refname"],
        capture_output=True, text=True, cwd=cwd,
    )
    for line in result.stdout.strip().splitlines():
        tag = line.strip()
        if tag:
            return tag
    return None
