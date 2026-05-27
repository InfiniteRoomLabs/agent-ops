# Testing

How testing works in agent-ops, the standards we hold code to, and the manual
end-to-end checks we haven't automated yet.

The testable surface here is `scripts/*.py` (the guards, hooks, and tooling). The
agent/skill/command Markdown files are not unit-tested.

## Running the suite

```bash
uv run pytest                                   # everything
uv run pytest tests/test_changelog_guard.py -q  # one file
```

Config lives in `pyproject.toml`: `testpaths = ["tests"]`, `pythonpath = ["scripts"]`,
and the dev dependency group pins `pytest>=8`. No CI job runs pytest today (only
`.github/workflows/auto-tag.yml`), so run it locally before committing. (Adding a pytest
CI gate is a future follow-up.)

## Layout & conventions

- `tests/test_<script>.py` mirrors `scripts/<script>.py`. Name mapping: take the basename,
  drop `.py`, replace `-` with `_`, prepend `test_`.
  - `changelog-guard.py` -> `tests/test_changelog_guard.py`
  - `auto-tag.py` -> `tests/test_auto_tag.py`
- `scripts/_shared/*.py` library modules use a different convention:
  `tests/test_shared_<name>.py` (e.g. `_shared/git_ops.py` -> `test_shared_git_ops.py`).
- Hyphenated script names can't be imported normally. Load them via
  `importlib.util.spec_from_file_location` -- see the pattern at the top of
  `tests/test_changelog_guard.py`.
- Scripts carry their runtime deps as PEP 723 inline metadata (`# /// script`) so
  `uv run scripts/x.py` self-resolves. `pyproject.toml` mirrors those deps only so the
  editor's language server can resolve imports.
- Shared fixtures live in `tests/conftest.py`: `git_repo` (inits a repo on `main` with an
  initial commit), `tagged_repo` (adds `v1.0.0`), `repo_with_manifest` (adds a
  `package.json`).
- Renaming a script: rename its test in the same commit. The coverage guard skips renames
  (it won't demand a brand-new test), but the suite will fail loudly on the stale import
  if you forget.

## Testing hook entrypoints

PreToolUse hooks read a JSON payload on stdin:

```json
{"tool_name": "Bash", "tool_input": {"command": "<the command>"}}
```

Exit `2` blocks the tool call (message goes to stderr); exit `0` allows it. You can drive
a hook directly:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git push origin main"}}' \
  | uv run scripts/changelog-guard.py hook
```

## Testing standards

The bar for code in `scripts/`. S1 is machine-enforced (see below); the rest are enforced
in review.

- **S1 - Coverage.** Every newly-added top-level `scripts/*.py` ships with its
  `tests/test_<name>.py` in the same change. Enforced by `scripts/test-coverage-guard.py`.
  S1 enforces *existence*, not quality -- a stub test passes the guard but fails S2-S4 in
  review.
- **S2 - Pure core, thin adapter.** Put logic in functions that return data or
  `(bool, str)` (e.g. `evaluate`, `evaluate_push`, `expected_test_path`). Keep the Typer
  commands (`hook`, `check`) as thin wrappers. Test the core directly.
- **S3 - Hook exit-code contract.** `0` allows, `2` blocks, the block message goes to
  stderr. Test both paths.
- **S4 - Hermetic & deterministic.** Automated tests do no network, use no real remote,
  and never depend on the current working directory or the wall clock. Pass `root=`,
  inject `today=`, inject collaborator functions (e.g. `evaluate(..., present=...)`).
  Anything that needs a network or a real remote belongs in Manual Tests below.
- **S5 - Manual tests are tracked debt.** Each manual entry names what blocks its
  automation and the trigger that would let it become a pytest case.

### How S1 enforcement works (and how to opt out)

`scripts/test-coverage-guard.py` runs on `git commit` (PreToolUse). It inspects the
staged tree, finds files added (status `A`) under top-level `scripts/`, and blocks the
commit if any lacks its `tests/test_<name>.py` (tracked or staged in the same commit).
Renames and modifications are ignored, as are `scripts/_shared/`, dunder files, and
anything in the `EXEMPT` set.

The guard only enforces in repos that have opted in by having a `tests/` directory at the
root. Repos that merely carry a `scripts/` dir (and the agency plugin) are left alone.

To exempt a genuinely test-free script, add its basename to `EXEMPT` in
`scripts/test-coverage-guard.py` with a one-line reason.

## Manual tests

End-to-end checks that aren't automated yet. Run them by hand against throwaway repos on
`/dev/shm` (tmpfs). Promote an entry to a pytest case once the blocker named below is
gone.

### M1 - changelog-guard push protection (real repo + remote)

**Purpose:** confirm the `hook` entrypoint blocks a real push to a protected branch when
no `CHANGELOG.md` is tracked, and allows it (and a real `git push` to a bare remote
succeeds) once `CHANGELOG.md` is committed. Covers the clone -> branch -> merge -> push
gap that the push guard closed.

**Blocks automation:** needs a real remote and a real `git push`, which S4 forbids in the
suite. **Promote when:** a hermetic bare-remote fixture exists in `conftest.py`.

```bash
#!/usr/bin/env bash
set -euo pipefail
GUARD="$HOME/projects/infinite-room-labs/agent-ops/scripts/changelog-guard.py"
WORK=$(mktemp -d -p /dev/shm changelog-guard.XXXXXX)
trap 'rm -rf "$WORK"' EXIT

git init -q --bare "$WORK/remote.git"
git clone -q "$WORK/remote.git" "$WORK/repo"
cd "$WORK/repo"
git config user.email t@t.co && git config user.name T
echo "# demo" > README.md && git add README.md && git commit -qm "init"
git branch -M main

run_hook() {  # $1 = command; prints ALLOWED or "BLOCKED rc=N"
  echo "{\"tool_name\":\"Bash\",\"tool_input\":{\"command\":\"$1\"}}" \
    | uv run "$GUARD" hook && echo "ALLOWED" || echo "BLOCKED rc=$?"
}

echo "== push main, no tracked CHANGELOG (expect BLOCKED rc=2) =="
run_hook "git push origin main"
echo "== push feature branch (expect ALLOWED) =="
run_hook "git push origin feature/x"
echo "== delete :main (expect ALLOWED) =="
run_hook "git push origin :main"

echo "== commit CHANGELOG, then push main (expect ALLOWED) =="
# committing the example template is fine here -- we test the guard, not the content
git add CHANGELOG.md && git commit -qm "docs: changelog"   # template generated by first block
run_hook "git push origin main"

echo "== real push to bare remote (expect success) =="
git push -q origin main && echo "PUSH OK"
git -C "$WORK/remote.git" log --oneline -1
```

**Expected:** case 1 prints `BLOCKED rc=2`; feature-branch and delete cases print
`ALLOWED`; after committing the generated `CHANGELOG.md`, the push case prints `ALLOWED`
and the real push prints `PUSH OK` with the remote showing the commit.
