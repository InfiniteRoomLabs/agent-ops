"""Tests for scripts/resolve-redaction-terms.py. Fixtures use obviously fake terms only."""

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
        "resolve_redaction_terms", _SCRIPTS / "resolve-redaction-terms.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mod = _load_module()


def _write_claude_md(directory: Path, body: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "CLAUDE.md").write_text(body)


def test_parse_term_flag_only() -> None:
    assert mod.parse_term("acme-corp") == {"term": "acme-corp", "replacement": None}


def test_parse_term_mapping_form() -> None:
    assert mod.parse_term("acme-corp==>a former client") == {
        "term": "acme-corp",
        "replacement": "a former client",
    }


def test_load_terms_file_skips_comments_and_blanks(tmp_path: Path) -> None:
    f = tmp_path / "terms.txt"
    f.write_text("# comment\n\nacme-corp\ndr-fictional==>a provider\n")
    assert mod.load_terms_file(f) == ["acme-corp", "dr-fictional==>a provider"]


def test_load_terms_file_missing_is_tolerated(tmp_path: Path) -> None:
    assert mod.load_terms_file(tmp_path / "nope.txt") == []


def test_scope_union_not_override(tmp_path: Path) -> None:
    """Terms from every scope are unioned, unlike deep-merge list replacement."""
    home = tmp_path / "home"
    project = home / "projects" / "repo"
    _write_claude_md(home / ".claude", "---\npublic_readiness:\n  redaction_terms:\n    - acme-corp\n---\nx\n")
    _write_claude_md(home / "projects", "---\npublic_readiness:\n  redaction_terms:\n    - sister-repo\n---\nx\n")
    _write_claude_md(project, "---\npublic_readiness:\n  redaction_terms:\n    - repo-string\n---\nx\n")
    terms = mod.resolve_terms(cwd=project, home_override=home, env={})
    assert [t["term"] for t in terms] == ["acme-corp", "sister-repo", "repo-string"]


def test_env_file_comes_first(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = home / "repo"
    _write_claude_md(project, "---\npublic_readiness:\n  redaction_terms:\n    - acme-corp\n---\nx\n")
    env_file = tmp_path / "env-terms.txt"
    env_file.write_text("dr-fictional==>a provider\n")
    terms = mod.resolve_terms(cwd=project, home_override=home, env={mod.ENV_VAR: str(env_file)})
    assert [t["term"] for t in terms] == ["dr-fictional", "acme-corp"]
    assert terms[0]["source"] == "env"


def test_redaction_terms_file_key(tmp_path: Path) -> None:
    home = tmp_path / "home"
    terms_file = tmp_path / "private-terms.txt"
    terms_file.write_text("acme-corp==>a former employer\n")
    _write_claude_md(
        home / ".claude",
        f"---\npublic_readiness:\n  redaction_terms_file: {terms_file}\n---\nx\n",
    )
    terms = mod.resolve_terms(cwd=home, home_override=home, env={})
    assert terms == [
        {
            "term": "acme-corp",
            "replacement": "a former employer",
            "source": f"{home / '.claude' / 'CLAUDE.md'} -> {terms_file}",
        }
    ]


def test_missing_configured_terms_file_tolerated(tmp_path: Path) -> None:
    home = tmp_path / "home"
    _write_claude_md(home / ".claude", "---\npublic_readiness:\n  redaction_terms_file: /nope.txt\n---\nx\n")
    assert mod.resolve_terms(cwd=home, home_override=home, env={}) == []


def test_duplicate_lines_deduped(tmp_path: Path) -> None:
    home = tmp_path / "home"
    project = home / "repo"
    _write_claude_md(home / ".claude", "---\npublic_readiness:\n  redaction_terms: [acme-corp]\n---\nx\n")
    _write_claude_md(project, "---\npublic_readiness:\n  redaction_terms: [acme-corp]\n---\nx\n")
    terms = mod.resolve_terms(cwd=project, home_override=home, env={})
    assert len(terms) == 1


def test_nothing_configured_is_empty(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    assert mod.resolve_terms(cwd=home, home_override=home, env={}) == []
