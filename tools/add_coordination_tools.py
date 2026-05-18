#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Add cross-agent coordination tools to every agent frontmatter.

Tier 1 (all agents): SendMessage, TaskCreate, TaskGet, TaskUpdate, TaskList, TaskOutput
Tier 2 (leads/orchestrators): + TeamCreate, TeamDelete, TaskStop

Idempotent: skips agents that already have the full Tier 1 set.
Preserves original list format (bracketed vs comma).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"

TIER1 = ["SendMessage", "TaskCreate", "TaskGet", "TaskUpdate", "TaskList", "TaskOutput"]
TIER2_EXTRA = ["TeamCreate", "TeamDelete", "TaskStop"]

TIER2_AGENTS = {
    "core/ceo.md",
    "core/orchestrator.md",
    "core/reality-checker.md",
    "engineering/cto.md",
    "engineering/vp-engineering.md",
    "engineering/devops-manager.md",
    "engineering/security-lead.md",
    "engineering/incident-response-commander.md",
    "project-management/studio-producer.md",
    "project-management/project-shepherd.md",
    "project-management/studio-operations.md",
    "testing/qa-triage-lead.md",
    "testing/test-strategist.md",
    "product/sprint-prioritizer.md",
}

TOOLS_LINE_RE = re.compile(r"^tools:\s*(.+?)\s*$", re.MULTILINE)


def parse_tools(raw: str) -> tuple[list[str], bool]:
    """Return (tools_list, is_bracketed)."""
    stripped = raw.strip()
    bracketed = stripped.startswith("[") and stripped.endswith("]")
    if bracketed:
        stripped = stripped[1:-1]
    return [t.strip() for t in stripped.split(",") if t.strip()], bracketed


def render_tools(tools: list[str], bracketed: bool) -> str:
    joined = ", ".join(tools)
    return f"[{joined}]" if bracketed else joined


def process(path: Path, rel: str) -> str:
    text = path.read_text(encoding="utf-8")
    match = TOOLS_LINE_RE.search(text)
    if not match:
        return "SKIP no-tools-line"

    tools, bracketed = parse_tools(match.group(1))
    additions = list(TIER1)
    if rel in TIER2_AGENTS:
        additions += TIER2_EXTRA

    missing = [t for t in additions if t not in tools]
    if not missing:
        return "SKIP already-has-all"

    new_tools = tools + missing
    new_line = f"tools: {render_tools(new_tools, bracketed)}"
    new_text = text[: match.start()] + new_line + text[match.end():]
    path.write_text(new_text, encoding="utf-8")
    tier = "T2" if rel in TIER2_AGENTS else "T1"
    return f"OK {tier} +{','.join(missing)}"


def main() -> int:
    if not AGENTS_DIR.is_dir():
        print(f"missing dir: {AGENTS_DIR}", file=sys.stderr)
        return 1
    counts: dict[str, int] = {}
    for path in sorted(AGENTS_DIR.rglob("*.md")):
        rel = str(path.relative_to(AGENTS_DIR))
        result = process(path, rel)
        head = result.split()[0]
        counts[head] = counts.get(head, 0) + 1
        print(f"{rel}: {result}")
    print("---")
    for k, v in sorted(counts.items()):
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
