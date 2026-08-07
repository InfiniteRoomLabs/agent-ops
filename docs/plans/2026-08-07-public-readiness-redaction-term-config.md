# Plan: Configurable Redaction Terms for public-readiness (3-scope, 12-factor)

Status: executed 2026-08-07
Origin: a 2026-08-07 public-readiness audit of a private sister repo. The personal red-flag term sweep ran from terms that exist only in the operator's private global CLAUDE.md prose and the auditing agent's session context. Nothing in agent-ops carries them (verified: the only grep hits in this repo are generic English words in unrelated agent guidance). That is the right end state for the PLUGIN, but it means every audit re-derives the list ad hoc and a subagent without the operator's session context would miss them entirely.

## Goal

The `public-readiness` skill resolves its personal red-flag / redaction term list from configuration instead of session memory, using the existing agent-ops configuration system (`scripts/_shared/frontmatter_config.py`: CLAUDE.md YAML frontmatter, deep-merged global -> parent -> project, most-specific wins), plus a 12-factor env override.

## Non-negotiable constraint

**The term list itself is radioactive.** It names people, organizations, and terms private to the operator. It must NEVER appear in:
- this repo (the marketplace may itself go public one day),
- any project-scope CLAUDE.md of a repo being prepared for publication (self-leak),
- any plan, commit message, or test fixture.

Test fixtures use obviously fake terms (`acme-corp`, `dr-fictional`). This plan deliberately does not enumerate the real terms; they live in the operator's global `~/.claude/CLAUDE.md`.

## Design

### Config keys (YAML frontmatter in CLAUDE.md, any scope)

```yaml
---
public_readiness:
  redaction_terms:
    - "some-term"                 # flag-only: reviewed wherever found
    - "old-string==>replacement"  # mapping form: feeds git-filter-repo --replace-text directly
  redaction_terms_file: ~/.claude/public-readiness-terms.txt   # optional; one term/mapping per line, # comments
---
```

### Resolution order (first -> last, UNION not override)

1. `PUBLIC_READINESS_TERMS_FILE` env var (12-factor escape hatch; points at a file)
2. Global scope: `~/.claude/CLAUDE.md` frontmatter -- where personal terms belong
3. Parent scopes: intermediate CLAUDE.md files between home and the repo (e.g. `~/projects/infinite-room-labs/CLAUDE.md` for org-wide terms like private sister-repo names)
4. Project scope: the audited repo's CLAUDE.md -- ONLY for non-sensitive repo-specific strings, with a loud warning in the skill that project-scope terms are visible in the repo being published

Terms are a denylist: merge semantics are set-union across all scopes (frontmatter_config's deep-merge replaces lists -- do the union in the skill/helper layer, not by changing frontmatter_config's semantics, which other consumers rely on).

### Consumption in the skill

Update `skills/public-readiness/SKILL.md`:
- New section "Redaction term configuration" documenting the keys, scopes, union semantics, and the radioactivity constraint above.
- Step 1 (leak scan) instructs the agent to resolve the term list first (via the helper below or by reading the frontmatter hierarchy directly) and run it as an additional grep pass over working tree + all history + commit messages -- alongside, not replacing, the generic credential/topology greps.
- Step 5 (history scrub) instructs that any resolved term in `old==>new` mapping form goes straight into the `--replace-text` file.
- Terms without a mapping default to flag-for-human-review, not auto-redact (a term like a former employer's name may legitimately need judgment, e.g. anonymize vs delete the file).

### Optional helper (small, keeps skill deterministic)

`scripts/resolve-redaction-terms.py` (uv script, reuses `_shared/frontmatter_config.py`):
- Resolves all four sources, prints the unioned list to stdout (one per line), never logs to any file.
- `--json` flag for structured output (term, source-scope, has-mapping).
- Exit 0 with empty output when nothing is configured (skill falls back to generic scan only).
- pytest coverage in `tests/` with fake-term fixtures: scope union, mapping parse, env override, missing-file tolerance.

## Laptop-side change (operator machine, NOT this repo)

Add to `~/.claude/CLAUDE.md` frontmatter: a `public_readiness` block carrying the terms from the privacy rules already documented in that file's prose (the executing agent has access to that file and should derive the list from it, adding the mapping form where an obvious placeholder exists). That file is private to the machine, which is exactly the point of the global scope. Executed variant: the frontmatter block points at `~/.claude/public-readiness-terms.txt` (chmod 600) via `redaction_terms_file` instead of carrying terms inline -- this keeps the radioactive list out of the CLAUDE.md prose that gets injected into every agent session's context.

## Acceptance

1. `registry.yaml` untouched (skill already registered); SKILL.md documents the config; helper (if built) passes pytest.
2. Grep of this repo for any real personal term returns zero hits after the change (the constraint held).
3. A dry run of the skill's Step 1 in the private sister repo surfaces the original audit's personal-term findings WITHOUT the operator's session context (i.e., a fresh subagent resolves the terms purely from config).
4. Global CLAUDE.md frontmatter parses cleanly (`resolve_frontmatter()` returns the block; malformed YAML frontmatter would silently disable ALL frontmatter config for every consumer -- validate before finishing).
