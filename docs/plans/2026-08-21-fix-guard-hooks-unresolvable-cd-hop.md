# Fix: git guard hooks crash on unresolvable `cd` hop (`cd $P && git commit`)

**Agent prompt — paste as the task for a fresh session in this repo (`agent-ops`).**

## Bug

Three PreToolUse Bash hooks in the `agency` plugin (`changelog-guard.py hook`, `version_guard.py hook`, `commit_guard.py pre`) traceback on every Bash command shaped like:

```bash
P=~/projects/some-client-repo; cd $P && git add -A && git commit -qm "msg"
```

Observed live 2026-08-21 (two tool calls, three tracebacks each, "Failed with non-blocking status code"). Error:

```
FileNotFoundError: [Errno 2] No such file or directory: PosixPath('/home/<user>/$P')
```

raised from `subprocess.run(..., cwd=project_dir)` at `changelog-guard.py:308`, `commit_guard.py:370`, `version_guard.py:430`.

## Root cause

`scripts/_shared/git_ops.py`:

- `effective_cwd()` walks `cd <path>` hops before the first `git` token. `_apply_path()` does `os.path.expandvars("$P")`, but `$P` is assigned *inside the command*, not in the hook's env, so it stays literal → `Path('/home/<user>/$P')`.
- `get_repo_root()` catches its own `FileNotFoundError` and returns that nonexistent path as the fallback. Every downstream `subprocess.run(git ..., cwd=project_dir)` in the three guard scripts then raises — none of them catch it.
- The docstring of `effective_cwd` says non-expandable shell variables are "ignored"; in practice they poison the cwd.

Reproduce (from anywhere):

```bash
R=~/.claude/plugins/cache/infinite-room-labs/agency/1.18.0   # or this repo root
echo '{"tool_name":"Bash","tool_input":{"command":"P=~/x; cd $P && git commit -qm x"},"cwd":"/home/<user>","session_id":"t"}' \
  | CLAUDE_PLUGIN_ROOT=$R uv run $R/scripts/changelog-guard.py hook; echo exit=$?
```

Expect `exit=1` + traceback before the fix, `exit=0` after.

## Fix (keep it minimal)

1. In `effective_cwd()`: after a `cd` hop or `git -C` resolves, **if the resulting path is not an existing directory, keep the previous `cur` instead** (unresolvable hop = ignored, matching the docstring). Implement inside the loop, not just at the end, so a later relative hop chains off a real directory.
2. In `get_repo_root()`: if `fallback` is not an existing directory, fall back further to `Path.cwd()` — never return a path `subprocess` can't `chdir` into.
3. Do **not** try to emulate shell variable assignment (`P=...;` tracking). Out of scope; degrade gracefully instead.
4. Tests in `tests/test_shared_git_ops.py`: add cases for `cd $UNSET_VAR && git commit`, `cd /does/not/exist && git commit`, and `cd $UNSET && cd sub && git commit` (relative hop after a bad hop stays anchored to base). Assert `effective_cwd` returns the payload cwd / last good dir and that `resolve_repo_root` never returns a nonexistent path.
5. Run the repro above against the in-repo scripts (`R=$(pwd)`) and confirm `exit=0` for all three guards, and that the existing cross-repo case (`cd /real/other/repo && git commit`) still resolves to the other repo (that was the original reason for `effective_cwd`, see commit `4f6e862`).

## Release

- Bump the `agency` plugin patch version per `CONTRIBUTING.md` / `version_guard` rules; add a CHANGELOG.md entry **in the same commit** (one line, no wrapping).
- Follow the repo's normal release path so the installed plugin (`~/.claude/plugins/cache/infinite-room-labs/agency/<ver>`) picks it up; note in the final report whether a `claude plugin update` / reinstall is needed.

## Scope guard

Only `scripts/_shared/git_ops.py`, its tests, CHANGELOG, version bump. Don't touch the guard scripts' own logic unless a one-line `try/except` around their `subprocess.run` is genuinely needed after (1)+(2) — it shouldn't be.
