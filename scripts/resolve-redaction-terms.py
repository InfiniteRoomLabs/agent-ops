# /// script
# dependencies = ["typer>=0.12", "pyyaml>=6"]
# ///
"""Resolve the public-readiness redaction term list from configuration.

Sources, unioned in order (set-union, NOT most-specific-wins):
  1. ``PUBLIC_READINESS_TERMS_FILE`` env var (12-factor escape hatch)
  2. Every CLAUDE.md in the hierarchy (global -> parents -> project), reading
     ``public_readiness.redaction_terms`` (inline list) and
     ``public_readiness.redaction_terms_file`` (one term per line, # comments)

Term forms:
  ``some-term``                  flag-only: reviewed wherever found
  ``old-string==>replacement``   mapping: feeds git-filter-repo --replace-text

Prints the unioned list to stdout, one term per line. Never writes to any
file. Exits 0 with empty output when nothing is configured.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Mapping
from pathlib import Path

import typer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _shared.frontmatter_config import find_claude_md_files, parse_frontmatter  # noqa: E402

ENV_VAR = "PUBLIC_READINESS_TERMS_FILE"
MAPPING_SEP = "==>"

app = typer.Typer(add_completion=False)


def parse_term(line: str) -> dict:
    """Parse one term line into {term, replacement}."""
    if MAPPING_SEP in line:
        term, replacement = line.split(MAPPING_SEP, 1)
        return {"term": term, "replacement": replacement}
    return {"term": line, "replacement": None}


def load_terms_file(path: Path) -> list[str]:
    """Read one-term-per-line file; skip blanks and # comments. Missing file -> []."""
    try:
        lines = path.expanduser().read_text().splitlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")]


def resolve_terms(
    cwd: Path | None = None,
    home_override: Path | None = None,
    env: Mapping[str, str] | None = None,
) -> list[dict]:
    """Union terms from env file + every CLAUDE.md scope. Order-preserving dedupe."""
    env_map: Mapping[str, str] = os.environ if env is None else env
    raw: list[tuple[str, str]] = []  # (line, source)

    env_file = env_map.get(ENV_VAR)
    if env_file:
        raw.extend((ln, "env") for ln in load_terms_file(Path(env_file)))

    for md in find_claude_md_files(cwd or Path.cwd(), home_override=home_override):
        fm = parse_frontmatter(md.read_text()) or {}
        pr = fm.get("public_readiness") or {}
        if not isinstance(pr, dict):
            continue
        source = str(md)
        terms = pr.get("redaction_terms") or []
        if isinstance(terms, list):
            raw.extend((str(t), source) for t in terms)
        terms_file = pr.get("redaction_terms_file")
        if terms_file:
            raw.extend((ln, f"{source} -> {terms_file}") for ln in load_terms_file(Path(str(terms_file))))

    seen: set[str] = set()
    result: list[dict] = []
    for line, source in raw:
        if line in seen:
            continue
        seen.add(line)
        result.append({**parse_term(line), "source": source})
    return result


@app.command()
def main(
    as_json: bool = typer.Option(False, "--json", help="Structured output: term, source, has-mapping."),
    cwd: Path = typer.Option(Path("."), "--cwd", help="Directory to resolve the CLAUDE.md hierarchy from."),
) -> None:
    terms = resolve_terms(cwd=cwd.resolve())
    if as_json:
        typer.echo(json.dumps(terms, indent=2))
        return
    for t in terms:
        line = t["term"] if t["replacement"] is None else f"{t['term']}{MAPPING_SEP}{t['replacement']}"
        typer.echo(line)


if __name__ == "__main__":
    app()
