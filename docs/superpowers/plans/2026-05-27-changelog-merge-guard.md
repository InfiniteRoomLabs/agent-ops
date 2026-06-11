# TODO: extend changelog-guard to cover merges into protected branches

Status: idea capture (expand later)

## Gap
`changelog-guard.py` currently guards only two Bash events on protected
branches (`main`/`master`/`release/*`): `git commit` (CHANGELOG.md must be
staged) and `git push` (CHANGELOG.md must exist). A **`git merge` into a
protected branch** sidesteps both -- a fast-forward or merge commit can land
feature work on master with no CHANGELOG entry. (Hit this live: bulk/partial
MCP work merged to master, CHANGELOG forgotten until caught by hand.)

## Idea
1. **PostToolUse (Bash) hook**: detect a `git merge` (or checkout-of-protected
   followed by merge / FF) that advances a protected branch, and emit
   instructions telling the agent to update CHANGELOG.md for the newly merged
   commits before pushing. Non-blocking nudge (PostToolUse can't veto), so it
   must be loud + actionable (list the merged commit subjects so the agent can
   summarize them).
2. **PreToolUse (Bash) hook**: when a merge into a protected branch is about to
   happen, expect a CHANGELOG update to accompany/follow it -- e.g. block the
   subsequent `git push` of a protected branch whose newly merged range touched
   code but not CHANGELOG.md (extend the existing push-check from "exists" to
   "covers the merged range").

## Open questions (for later)
- Detecting "merge into protected" reliably across FF vs `--no-ff` vs squash.
- PostToolUse can only advise; real enforcement lives in the PreToolUse
  push-check. Decide the split.
- Range diff: did the merged commits change tracked code (not just docs)? Reuse
  `_shared/git_ops` + `_shared/changelog`.
- Test coverage in `tests/test_changelog_guard.py`.

Touches: `scripts/changelog-guard.py`, `hooks/hooks.json` (add PostToolUse Bash
matcher), `tests/test_changelog_guard.py`.
