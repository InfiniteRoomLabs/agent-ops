---
name: public-readiness
description: "Use when taking a private repo public, open-sourcing internal tooling, or auditing a repo before flipping its visibility. Triggers on 'make this public', 'before we open-source', 'is this safe to publish', 'public readiness review', or preparing a repo for a marketplace/showcase. Covers secret/topology leak scanning (working tree AND git history), license and OSS-health checks, doc accuracy, and history-scrub guidance."
argument-hint: "[repo path]"
tags:
  function: [engineering]
  scenario: [open-source, release-management]
  custom: [security, secrets, oss-health, public-release, git-history]
---

# Public Readiness Review

> If you see unfamiliar placeholders or need to check which tools are connected, see [CONNECTORS.md](../../CONNECTORS.md).

Audit a repository before it goes public. Find what must not ship (leaks), what must exist (license, community files), and what is wrong (stale docs) -- then scrub leaks from history, not just the working tree.

## Iron Law

**A WORKING-TREE FIX IS NOT A FIX. Leaks live in every past commit.** Deleting a secret from `HEAD` leaves it in history, branches, and tags. Nothing is "ready" until the CRITICAL leak list is empty across **all reachable history on every remote**. Never flip visibility to public while a CRITICAL item is open.

## Order matters: scrub while you still can

Check visibility first. The fix is free before publication and lossy after.

- **Private, 0 forks, never public** -> rewriting history now means nobody ever saw the leak. Do it before flipping public.
- **Already public / forked / mirrored** -> assume the data is out (cached, cloned, indexed). Rewrite still helps the future, but treat any real credential as compromised and **rotate it**, do not just delete it.

```bash
gh repo view OWNER/REPO --json visibility,isPrivate,forkCount,pushedAt
```

## Step 1: Leak scan (the blocker)

Scan **both the working tree and history**. Sort findings by category; only real credentials are "rotate now", the rest are "scrub before public".

| Category | What to grep for | Severity |
|----------|------------------|----------|
| Credentials | `api[_-]?key`, `secret`, `token`, `password`, `BEGIN ... PRIVATE KEY`, long base64/hex literals | CRITICAL + rotate |
| Network topology | internal/VPN IPs (e.g. Tailscale `100.x`), `:30000`-range NodePorts | CRITICAL |
| Internal domains | `*.internal.*`, `*.lab.*`, private DNS names | CRITICAL |
| Private paths/repos | `$HOME/...` absolute paths, names of private sister repos | HIGH |
| Personal identifiers | real names, nicknames, emails baked into agent/config files | MEDIUM |

```bash
# Working tree (tracked files only):
git grep -nIE "(api[_-]?key|secret|token|password|BEGIN .*PRIVATE KEY)" -- .
git grep -n "100\.[0-9]" -- .                 # adjust to your internal ranges
git grep -ni "internal\.\|\.lab\.\|<private-repo-name>" -- .

# History + how many commits each leak touches:
for s in "<LEAK_STRING>" "<ANOTHER>"; do
  printf "%-30s %s commits\n" "$s" "$(git log --oneline -S"$s" --all | wc -l)"
done
# Commit MESSAGES too (replace-text only fixes file content):
git log --all --format='%H %s%n%b' | grep -in "<LEAK_STRING>"
```

Fix the working tree first (replace each leak with a placeholder like `<HOMELAB_IP>`, `<your-infra-repo>`). Delete environment-specific hooks/scripts that only work on the author's machine -- they leak paths and are dead weight for everyone else. Then proceed to the history scrub (Step 5) if any leak appeared in a past commit.

## Step 2: License

- A repo with **no LICENSE file is all-rights-reserved** by default -- nobody may legally use it. GitHub shows "No license".
- Add a `LICENSE` (MIT is the safe default for a showcase; Apache-2.0 if you want explicit patent/attribution terms).
- Fix the README's license section to match -- a section saying "Private / internal use" actively contradicts an open-source release.
- If the project vendors third-party code, add attribution (NOTICES) for it.

## Step 3: OSS health

Delegate the community-standards sweep to the **oss-health-checker** agent, or check manually:

- `LICENSE` (Step 2), `README` (what it is, install, quick start, license, contributing link)
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`, issue + PR templates
- `.gitignore` keeps secrets, `.env`, agent dirs, and build artifacts out
- **CI actually runs the tests** -- a workflow that builds but never runs `pytest`/`jest` is a promise with no enforcement
- No internal-only directories committed without explanation

## Step 4: Doc accuracy

Stale docs read as careless in a showcase. Cross-check every count and claim against reality:

```bash
# Example: does the README's agent count match the filesystem?
find agents -name '*.md' | wc -l
git grep -n "[0-9]\+ specialized\|[0-9]\+ agents" -- README.md CLAUDE.md
```

Verify described structure, commands, and skills exist; verify any "discovers X via Y" architecture claim is actually true.

## Step 5: History scrub (use git-filter-repo, NOT filter-branch)

`git filter-branch` is deprecated and footgun-prone. Use `git-filter-repo` (`uvx git-filter-repo` or `pipx install git-filter-repo`).

```bash
# 1. Commit the working-tree fixes first (filter-repo needs a clean tree).
# 2. Write a replacement map (one per line, old==>new):
cat > /tmp/redactions.txt <<'EOF'
100.86.213.22==><HOMELAB_IP>
internal.example.com==><your-internal-domain>
chairman-jane==>on-call-human
EOF
# Put the most-specific strings first (auth.host before host).

# 3. Rewrite ALL commits + tags:
git filter-repo --replace-text /tmp/redactions.txt --force

# 4. filter-repo strips remotes by design -- re-add them:
git remote add origin <url>            # restore any dual-push config too

# 5. Verify zero hits remain, then force-push:
for s in "<LEAK_STRING>"; do git log --oneline -S"$s" --all | wc -l; done   # expect 0
git push origin main --force
git push origin --tags --force

# 6. Delete stale remote branches -- they still carry pre-rewrite history:
git ls-remote --heads origin                 # list what exists
git push origin --delete <stale-branch> ...
```

`--replace-text` rewrites file **content**, not commit messages -- if a leak is in a message, also pass a `--message-callback` or amend. After rewriting, every SHA changes; this breaks anyone who cloned, which is exactly why you do it while the repo is still private.

## Output: prioritized report

Lead with the verdict (publishable / not), then a severity-sorted table:

- **CRITICAL** -- leaks (rotate any real credential), no LICENSE: blocks publication
- **HIGH** -- missing community files, CI not running tests, stale "private" framing
- **MEDIUM/LOW** -- doc count drift, missing badges, polish

End with the single next action, not a survey of options.

## Common mistakes

- Scrubbing `HEAD` and calling it done -- the leak is still in history (the Iron Law).
- Using `git filter-branch` -- deprecated; use `git-filter-repo`.
- Forgetting tags and stale feature branches -- they preserve the old leaked commits after `main` is rewritten.
- Treating a topology leak as "just delete it" but a real credential the same way -- credentials that ever shipped must be **rotated**, not just removed.
- Genericizing an environment-specific hook instead of deleting it -- if it only runs on the author's machine, it is noise everywhere else.
