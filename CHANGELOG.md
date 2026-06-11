# Changelog

All notable changes to the agent-ops marketplace will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [agency-1.17.0] - 2026-06-11

### Changed
- **`skills/persona-forge/SKILL.md` gains Phase 3.5: persist every forged persona to `~/.claude/agents/<persona-slug>.md`.** Persistence is now a standard step (agent-definition format: frontmatter + spec-as-system-prompt + one provenance line: forge date, task, Phase 2 kills), replacing the old optional "consider promoting" advice. Re-forges of the same role version the existing file in place. Promotion to a permanent marketplace agent in `agents/{division}/` stays a separate deliberate act for multi-use-proven specs. (First beneficiary: `story-gap-auditor-marta`, forged 2026-06-11 for the Employa-Bot story-corpus gap hunt.)
- **`skills/release-prep/SKILL.md` gains Step 0: check for repo-local release tooling.** The generic skill told agents to hand-edit manifest files, contradicting repo conventions like this repo's own `tools/version_bump.py` mandate -- and a repo attached via `/add-dir` does not auto-load its CLAUDE.md, so the convention was invisible. Step 0 now requires reading the target repo's CLAUDE.md and hunting for bump/release tooling before the generic steps; Step 4 defers to whatever Step 0 found. (Hit live during the v1.16.0 release of this very repo.)

## [agency-1.16.0] - 2026-06-11

### Fixed
- **`config-tamper-guard.py` actually works now -- full rework against the official ConfigChange spec.** The old hook treated the stdin payload as the new settings content, but ConfigChange delivers a METADATA ENVELOPE (`config_source`, `changed_keys`, `file_path`) -- so every legit settings change was diffed against the envelope and falsely flagged; worse, the snapshot was overwritten with the envelope even after a block, leaving the guard permanently blind. Rework: content is read fresh from the payload's `file_path`; snapshots are kept PER SOURCE (`settings-snapshot-{user,project,local}_settings.json`) so a local-settings change is never judged against a project baseline (the stale single-file snapshot is cleaned up at SessionStart); blocks do NOT advance the snapshot (Claude Code reverts the file, so the baseline stays true); weaken-detection is recursive (`find_weakenings`: removals/modifications at any depth under a protected key; additions always allowed; canonical-JSON multiset diff for lists, so list-of-dicts no longer raises TypeError); a kill-switch denylist (`enforcement.blocked_settings`, default `["disableAllHooks"]`) blocks dangerous ADDITIONS, including in a brand-new settings file; failure policy is fail-closed (any evaluation error exits 2, reverting the unjudged change); and blocked changes plus out-of-scope sources (`policy_settings`, `skills`) are audit-logged to `config-changes.jsonl`. The hooks.json source matcher is gone -- the script's `SOURCE_FILES` is the single owner of which sources are judged.
- **`_shared/paths.py` slug rule now matches Claude Code's.** `cwd_slug` replaced only `/` with `-`; Claude Code replaces EVERY non-alphanumeric character (verified live 2026-06-11: a session in `/tmp/slug.test_x` lands in `~/.claude/projects/-tmp-slug-test-x`, while our hooks had minted a ghost `-tmp-slug.test_x` dir one second earlier). Latent for all current dot-free repo paths; real for any dotted/underscored cwd -- audit logs and tamper snapshots were landing in a parallel dir Claude Code never reads.
- **Slug anchoring is now shared, not per-script.** New `_shared/paths.project_dir()` prefers `CLAUDE_PROJECT_DIR` over the process cwd, and `cwd_slug()`/`get_audit_dir()` key off it by default -- previously only `summon.py` did this (inline), so a ConfigChange fired from a subdir/worktree could resolve a different slug than the SessionStart snapshot, silently adopting a tampered file as a fresh baseline. `summon.get_state_dir` now delegates to the shared rule.

- **Guards are now cwd-aware -- cross-repo git commands are judged against the repo they target, not the session repo.** Observed live 2026-06-10: `cd <other-repo> && git commit` was falsely blocked because changelog-guard checked the SESSION repo's branch and staged index. New `_shared/git_ops.py` helpers: `effective_cwd(command, payload_cwd)` (resolves the payload `cwd` plus any `cd <path>` hops and `git -C <path>`, with offset-preserving quote masking so quoted text can't inject phantom `cd`s or stop resolution early), `get_repo_root(cwd)`, `resolve_repo_root(command, payload_cwd)` (the one hook entry point), and cwd params on `get_current_branch`/`get_latest_tag`/`get_staged_files`. All four guards (`changelog-guard.py`, `version_guard.py`, `commit_guard.py`, `test-coverage-guard.py`) now read the hook payload's `cwd` field and thread the resolved repo through every git call.
- **`git commit -a/-am/--all` is now rejected on protected branches** (new `is_self_staging_commit` + `stages_at_commit_time` in `git_ops.py`): self-staging commits record a different index than the one the guards inspected pre-commit -- the same staleness hole as combined add+commit, previously documented as an out-of-scope gap. `--amend` does not match.
- **Combined add+commit is no longer blocked on unprotected branches.** The staging-separation rule exists to serve the protected-branch checks; feature-branch commits now pass through. (changelog-guard checks its hard-coded protected set; version_guard checks its per-repo config.)
- **`test-coverage-guard.py` hook now uses skeleton-based command detection** (`runs_git_command`) instead of a raw-substring regex -- a commit MESSAGE mentioning "git commit" no longer triggers evaluation (same fix class as v1.15.1).
- **`auto-tag.py` no longer tags-and-pushes on text that merely mentions `gh pr merge`, on failed merges, or at the wrong commit.** The trigger matched the RAW command, so echoed text/heredocs could fire a hook that pushes release tags -- detection is now skeleton-based (`shell_command_skeleton`). PostToolUse fires for failed commands too: the hook now inspects the payload's `tool_response` and treats absent/ambiguous response data as failure (do nothing). The cwd split-brain is closed: the project dir comes from `resolve_repo_root(cmd, payload.cwd)` instead of `Path.cwd()`, and is threaded through `get_latest_tag` and `create_and_push_tag`. And since the local checkout is the stale feature branch right after a PR merge, the hook now fetches origin and tags the remote default branch head (`origin/HEAD`, falling back to the current branch's upstream) -- if detection fails it logs and skips rather than tag the wrong commit.
- **`teammate-gate.py` now validates the teammate's tree, not the hook process's.** `idle`/`completed` never read the stdin payload and ran `git status --porcelain` in the process cwd, so teammates in worktrees were judged against the WRONG TREE (security checks silently bypassed, or clean teammates blocked for other agents' files). Both entrypoints now parse the payload's `cwd` (malformed/missing input falls back to the process cwd), run git there, resolve file paths against it, and pass it to frontmatter config resolution. File discovery uses `git status --porcelain -z --untracked-files=all`: files inside new untracked directories are now seen, and spaced/quoted paths survive unmangled.
- **`summon.py` state files are no longer instantly stale.** `state create` minted a random `session_id`, so whenever `CLAUDE_SESSION_ID` was set, every state file mismatched at check time and SessionStart clean deleted LIVE personas. It now uses `CLAUDE_SESSION_ID` when present (random UUID fallback), per the implementation plan. The default state dir is keyed to `CLAUDE_PROJECT_DIR` (falling back to process cwd) so subshell/worktree invocations share one slug, and the state write is atomic (tmp file + `os.replace`). New `tests/test_summon.py` covers session-id sourcing, staleness, clean-if-stale, and write atomicity.
- **`worktree_lifecycle.py` creates `.worktrees/` at the repo root, and branchless payloads no longer crash.** `create` used `Path.cwd()` directly, so a session started in a subdirectory grew a nested `.worktrees/` there and hook propagation silently no-opped; it now resolves the root via `git_ops.get_repo_root`. `CreatePayload.branch` is optional (defaults to empty) to match the existing `if payload.branch:` guard instead of rejecting the payload outright.
- **`elicitation-gate.py` and `instructions-guard.py` no longer traceback on malformed stdin.** instructions-guard's hook exits 0 (advisory contract). elicitation-gate's `request` fails CLOSED when block patterns are configured -- it emits its decline, since a malformed payload must not become a bypass -- and exits 0 otherwise; `result` (audit-only) exits cleanly.
- **`_shared/changelog.py` reads `CHANGELOG.md` as UTF-8 explicitly** (both `read_text()` calls) instead of relying on the locale default encoding.

### Removed
- **`worktree_lifecycle.py` `clean_branches` config field.** Designed in the 2026-03-18 hook-enforcement architecture (opt-in destructive orphan-branch cleanup on WorktreeRemove) but never implemented -- dead config promising behavior that didn't exist. Dropped from `WorktreeConfig` and the design doc; orphaned merged branches are a manual `git branch -d` away.

### Changed
- **`README.md` now documents output style registration.** New "Output Styles" section: plugin-shipped styles register plugin-namespaced (`agency:ADHD Accessibility`); the plain style name silently falls back to the default style, and a project-level `outputStyle` in `.claude/settings(.local).json` overrides the user-level setting. Covers `/output-style` and `settings.json` activation paths. Found live 2026-06-11: both gotchas together kept the ADHD style from ever loading.
- **Guard hot path is cheaper**: repo resolution runs only after the is-this-git gates (non-git Bash calls spawn zero subprocesses again); `shell_command_skeleton` is lru_cached (it was recomputed up to 4x per invocation); version_guard resolves the branch once per hook fire and passes it into `evaluate()`; the staging-separation message and the protected-branches default regex are single shared definitions (`STAGING_SEPARATION_MESSAGE`, `PROTECTED_BRANCHES_DEFAULT`) instead of per-guard copies.
- **`hooks/pre-deploy-secrets-sync.sh`** -- aligned with the 2026-05 fnox migration: Bitwarden session resolution now goes env `BW_SESSION` -> `fnox get BW_SESSION` (age-backed) -> the fish `bw-unlock` cache at `~/.bw_session` (the old `~/.secrets/bw-session` path is gone); when `with-secrets.sh` exists the ansible sync runs through the fnox-exec wrapper so it sees all declared secrets.

### Added
- **`agents/research/calm-company-underwriter.md`** -- first persona-forge graduate, promoted per the skill's "promote proven specs" path after the 2026-06-10 Employa-Bot viability engagement: a bootstrap-business viability underwriter with scar-derived heuristics (churn-on-success cohort math, structural-vs-keynote-away differentiator sort, attention-runway audit, institutional B2B2C costing), declared retained biases, named blind spots, and an out-of-character contract (bias footnote + personal-context-never-enters-repos rule). Registered in `registry.yaml`.
- **`docs/plans/2026-05-27-shellcheck-lint-hook-explore.md`** -- exploration prompt (not a committed plan): surface shellcheck findings automatically when agents write/edit `*.sh` -- investigate bash-language-server LSP vs a PostToolUse hook; pick up in a fresh session.
- **`docs/superpowers/plans/2026-05-27-changelog-merge-guard.md`** -- idea capture: `changelog-guard.py` guards `git commit` and `git push` on protected branches but a `git merge` into a protected branch sidesteps both (hit live). Sketches PostToolUse nudge + PreToolUse veto approaches.
- **`skills/persona-forge/SKILL.md`** -- new skill: forge the right worker before working. For any role-shaped task (analysis, review, writing, architecture, negotiation, teaching), generates 3-5 candidate personas, antagonistically attacks each for bias/blind spots, evolves survivors through at least two merge-attack-refine rounds into one optimal persona spec (with declared retained biases and named blind spots), then the parent agent adopts it for the work phase and closes with an out-of-character bias footnote. Proven specs can be promoted to permanent `agents/{division}/` definitions. Registered in `registry.yaml`.

## [agency-1.15.1] - 2026-05-27

### Fixed
- **Guard command detection no longer false-triggers on message text.** `changelog-guard`, `version_guard`, and `commit_guard` detected `git commit`/`git add` by substring-matching the raw command, so a commit whose *message* mentioned "git add" (or an echoed JSON payload containing "git commit") was misread -- e.g. the combined-add+commit rejection firing on a commit message that merely said "the git add step". New shared helpers in `_shared/git_ops.py` (`shell_command_skeleton`, `runs_git_command`, `is_combined_add_commit`) strip heredoc bodies and quoted spans before the detection regexes run, so they see command structure rather than argument/message text. All three guards now route their `git add`/`git commit`/`git tag`/`git push` detection and the combined-add+commit check through these helpers. Note: `git commit -a`/`-am` still bypass the combined check (no literal `git add` token) -- a pre-existing gap, documented in the helper, not addressed here.

## [agency-1.15.0] - 2026-05-27

### Added
- **`TESTING.md`** -- first testing documentation for the repo: how to run the suite, the layout/loader conventions, how to drive hook entrypoints, five testing standards (S1 coverage, S2 pure-core/thin-adapter, S3 hook exit-code contract, S4 hermetic+deterministic, S5 manual tests as tracked debt), and a "Manual Tests" section. First manual entry M1 documents the changelog-guard push protection end-to-end check (real repo + bare remote on `/dev/shm`), which S4 keeps out of the automated suite until a hermetic remote fixture exists.
- **`scripts/test-coverage-guard.py`** -- machine-enforces standard S1: blocks a commit that adds a top-level `scripts/*.py` without its matching `tests/test_<name>.py` (tracked or staged). Renames/modifies and `scripts/_shared/` are skipped; an `EXEMPT` set allows opt-outs. Pure core `evaluate(added, present)` with an injected presence check (S2/S4); covered by `tests/test_test_coverage_guard.py`. Wired **only** in this repo's `.claude/settings.json` (PreToolUse/Bash) -- deliberately NOT in the plugin's `hooks/hooks.json`, so the agent-ops-specific convention never fires in the other repos the agency plugin is installed in.

### Changed
- **`.gitignore`** -- `.claude/` contents stay ignored, but `.claude/settings.json` (and `.claude/.gitignore`) are now re-included so the shared project hook config is committed; `.claude/settings.local.json` remains personal/ignored.
- **`CLAUDE.md`, `README.md`** -- point to `TESTING.md` for testing and standards.
- **`.claude/settings.json`** -- consolidated the repo's dev-time PreToolUse guards (changelog-guard, version_guard) from personal `settings.local.json` into the shared, committed `settings.json` alongside test-coverage-guard, so every clone dogfoods the same guards while developing agent-ops.
- **`tests/test_changelog_guard.py`** -- assert the block messages actually instruct editing the generated template: the commit path warns the example is a placeholder (`placeholders`, `must not be committed as-is`), and the push generate-path tells the agent to `Edit it` and delete the `example block`.

## [agency-1.14.0] - 2026-05-27

### Added
- **`scripts/changelog-guard.py`** now guards `git push` in addition to `git commit`. When a push targets a protected branch (`main`/`master`/`release/*`) and the repo has no **tracked** `CHANGELOG.md`, the PreToolUse hook blocks it (exit 2). Closes the gap where you clone an existing repo with no changelog, branch, merge locally into `main`, and push -- none of those commits ever tripped the commit-time guard on a protected branch. The push check is laxer than the commit check by design: it only requires the changelog *exist as a tracked file*, since push time can't cheaply diff against the remote. New `resolve_push_targets()` parses the refspec (handles `git push`, `origin main`, `HEAD:main`, `:main` deletes, `--delete`, `--tags`, `--all`/`--mirror`), `evaluate_push()` runs the check, and a `push-check --command "..."` CLI command supports manual runs. A template is generated when `CHANGELOG.md` is absent from disk; the block message spells out the add/commit/push sequence (a generated-but-uncommitted file does not unblock the push).

## [agency-1.13.1] - 2026-05-20

### Fixed
- **`scripts/commit_guard.py`** -- `build/` no longer trips a false positive on non-Java repos. The pattern now requires evidence of a Gradle/Maven project (`build.gradle`, `pom.xml`, `gradlew`, `mvnw`, etc., at root or in any module) before flagging. Reasoning: `build/` is Gradle's canonical output dir, but many repos use `build/` for shell scripts, Docker build contexts, or CI helpers (e.g. amborle/featmap's `build/build_webapp.sh`) -- the basename alone is ambiguous. Mirrors the same predicate pattern already used for `packages/` (.NET vs. JS workspace).

### Added
- **`docs/superpowers/`** -- captures the plan and design spec behind the commit-guard predicate fix (`plans/2026-03-26-commit-guard.md`, `specs/2026-03-26-commit-guard-design.md`) so future passes have the reasoning, not just the diff.

## [agency-1.13.0] - 2026-05-18

### Added
- **Cross-agent coordination tools** added to all 155 agent frontmatters. Tier 1 (every agent): `SendMessage`, `TaskCreate`, `TaskGet`, `TaskUpdate`, `TaskList`, `TaskOutput` -- so any specialist can address peers by name and read/write the shared task board. Tier 2 (14 leads/orchestrators: CEO, Orchestrator, Reality Checker, CTO, VP Eng, DevOps Manager, Security Lead, Incident Commander, Studio Producer/Operations, Project Shepherd, QA Triage Lead, Test Strategist, Sprint Prioritizer): additionally `TeamCreate`, `TeamDelete`, `TaskStop` -- team-spawn and task-kill authority that maps to org-chart seniority. Converts the agency from a parent-only spawn tree into a peer-to-peer graph with a shared work board.
- **`tools/add_coordination_tools.py`** -- idempotent bulk-edit script that classifies agents by relative path, preserves original tools-list format (bracketed vs comma), and skips any agent already holding the full additive set. Safe to re-run as new agents land.

## [agency-1.12.2] - 2026-05-01

### Changed
- **CLAUDE.md** documents the release workflow: which files carry which version, when each bump level applies, and that `tools/version_bump.py` is the canonical way to update them. Future agents/sessions should use the script, not hand-edit, so plugin.json and pyproject.toml stay in sync and `uv.lock` gets refreshed.

## [agency-1.12.1] - 2026-05-01

### Added
- **`tools/version_bump.py`** -- repo-internal version bumper that updates `pyproject.toml`, `.claude-plugin/plugin.json`, and the agency entry in `.claude-plugin/marketplace.json` independently, with `--plugin`, `--pyproject`, `--marketplace`, and `--all` flags accepting `major|minor|patch` or `set:X.Y.Z`. Refreshes `uv.lock` automatically when `pyproject.toml` is touched. Warns when plugin and pyproject would diverge (the version-guard hook would block the resulting commit). Lives under `tools/` to flag it as not part of any plugin distribution surface.
- **`tests/test_version_bump.py`** -- 16 tests covering bump-level parsing, `set:X.Y.Z` overrides, file round-trips, and the typer-driven end-to-end paths (all/plugin-only/marketplace-only/dry-run/no-args).

## [agency-1.12.0] - 2026-05-01

### Added
- **`render-mermaid` skill** (`skills/render-mermaid/`) -- renders a mermaid diagram (from a `.mmd` file or piped stdin) and opens it in the user's default viewer. Defaults tuned for Linux + sandboxed browsers: PDF output (vector + baked fonts so text survives mermaid's CSS-variable rendering quirks in `eog`/Loupe and system dark mode), output written to `~/Downloads/` so snap/flatpak Firefox can read it, Puppeteer launched with `--no-sandbox` so Ubuntu 23.10+ AppArmor doesn't block Chromium. Description scoped tightly: triggers on "render/visualize/view/open/show me as a diagram" only -- not on plain mermaid authoring -- so it doesn't burn tokens when the user is just writing or editing mermaid source.
- **`scripts/templates/`** convention extended: skill-local helpers may now ship as siblings of `SKILL.md` (e.g. `skills/render-mermaid/render_mermaid.py`) rather than under `scripts/`. Inline PEP 723 dependency headers keep them runnable via `uv run`.

## [agency-1.11.1] - 2026-05-01

### Changed
- **CHANGELOG header** now matches the canonical Keep a Changelog 1.1.0 + Semantic Versioning 2.0.0 two-paragraph block emitted by `scripts/templates/CHANGELOG.template.md`. Project-specific phrasing ("agent-ops marketplace") preserved.

## [agency-1.11.0] - 2026-05-01

### Added
- **CHANGELOG bootstrap in `scripts/changelog-guard.py`** -- when committing on a protected branch with no `CHANGELOG.md` present, the guard now writes an example template to the repo root before blocking. The block message instructs the agent to keep the canonical 5-line header (title + Keep a Changelog + Semantic Versioning paragraphs), delete the example block, and replace it with real release entries.
- **`scripts/templates/CHANGELOG.template.md`** -- standalone artifact owning the template body. Single `{{DATE}}` placeholder; demonstrates all six Keep a Changelog section names (Added, Changed, Deprecated, Removed, Fixed, Security) across two example patch releases of a fictional `widget` CLI, plus an HTML comment describing what to keep and what to replace.
- **`tests/test_changelog_guard.py`** -- 10 tests covering template rendering, `{{DATE}}` substitution, file generation, and every branch of `evaluate()` including the no-overwrite guarantee when an existing CHANGELOG is present but unstaged.

## [agency-1.10.2] - 2026-05-01

### Added
- **Python dev environment** (`pyproject.toml`, `pyrightconfig.json`, `.zed/settings.json`) -- declares dev-only dependency manifest (`pydantic`, `typer`, `semver`, `pyyaml`, `pytest`) so editor LSPs (basedpyright/pyright) resolve imports for `scripts/` and `tests/`. Runtime scripts still use PEP 723 inline dependency headers and run via `uv run`. `pyrightconfig.json` pins venv path; `.zed/settings.json` forces basedpyright with `extraPaths=["scripts"]`.
- `.venv/` to `.gitignore`.

### Fixed
- **Builtin shadowing in `scripts/summon.py`** -- the Typer command `def list(...)` shadowed `builtins.list` at module scope, causing every `list[X]` annotation in the file to resolve to the function rather than the type. Renamed to `def list_agents` with `@app.command(name="list")` so the CLI surface is unchanged. Removed unused `import hashlib`.

## [agency-1.10.1] - 2026-04-30

### Changed
- **Marketplace entry** (`.claude-plugin/marketplace.json`) -- bumped agency plugin entry from 1.2.0 to 1.2.1 so the marketplace catalog reflects the commit-guard hotfix.

### Fixed
- **commit-guard `packages/` false positive** (`scripts/commit_guard.py`) -- the `.NET: packages/` rule was blocking commits in pnpm/npm/yarn/lerna/nx/turborepo workspaces where `packages/` is the standard source root. Heuristic now requires real .NET evidence (`.csproj`/`.sln`/`global.json`/`NuGet.Config`/legacy `<packages>` element in a csproj) before flagging, and skips entirely when JS workspace evidence is detected. Other .NET artifact dirs (`bin/`, `obj/`) remain unconditionally blocked. Reproduction case: `claudesync` repo at `~/projects/infinite-room-labs/claudesync` could no longer commit `packages/core/src/sync/state.ts`.

### Added
- **commit-guard regression tests** (`tests/test_commit_guard.py`) -- 18 tests covering pnpm/npm-workspaces/lerna/nx/turbo allowlists, modern + legacy `<packages>` .NET repos, unconditional `bin/`/`obj/` blocking, and detector unit coverage.
- **`requires` predicate field on `IgnoredPattern`** -- per-pattern context gate, evaluated once per repo and cached. Future ambiguous patterns can opt in without touching `find_violations`.

## [agency-1.10.0] - 2026-04-02

### Added
- **ADHD Accessibility output style** (`output-styles/adhd.md`) -- first-class output style replacing the old skill-based approach. All 9 behavioral rules (micro-chunking, reduced decisions, response brevity, momentum preservation, progress dopamine, context anchoring, anti-rabbit-hole guardrails, time awareness, sensory-friendly formatting) baked in with recommended defaults. Activate via `/config` -> Output style -> ADHD Accessibility.
- **Output styles support** in `plugin.json` -- `outputStyles` field pointing to `./output-styles/` directory

### Removed
- `skills/accessibility-adhd/SKILL.md` -- replaced by the ADHD output style
- `commands/init-adhd.md` -- no longer needed; output styles are selected via `/config`
- `scripts/accessibility-config.py` -- SessionStart hook detection no longer needed
- `accessibility-config.py` entry from SessionStart hooks in `hooks.json`
- `accessibility-adhd` and `init-adhd` entries from `registry.yaml`

### Changed
- `docs/guides/accessibility-adhd.md` rewritten to document the output style approach with migration instructions from the old skill-based system

## [agency-1.9.0] - 2026-03-26

### Added
- **7 new agents** closing coverage gaps across the software-house lifecycle:
  - `integration-engineer` (engineering) -- third-party SaaS integrations (Stripe, OAuth, S3, etc.)
  - `requirements-engineer` (product) -- structured requirements elicitation, PRDs, user story maps
  - `lead-finder` (research) -- ICP matching, prospect scoring, pipeline entry point
  - `debugger` (engineering) -- hypothesis-driven bug investigation with IRL stack awareness
  - `retro-facilitator` (project-management) -- sprint retros, kaizen metrics, action item tracking
  - `test-strategist` (testing) -- test pyramid selection, risk-based coverage targets
  - `qa-triage-lead` (testing, haiku) -- defect lifecycle, severity classification, routing
- **4 NEXUS quality gates**: scoping-complete, planning-complete, build-complete, release-readiness certificate
- **4 NEXUS-Micro runbooks**: post-deploy-handoff, sprint-planning, ux-design-sprint, support-escalation
- **12 handoff contracts** added to agents (proposal-strategist, project-shepherd, deal-strategist, feedback-synthesizer, outbound-strategist, requirements-engineer, integration-engineer, lead-finder, debugger, retro-facilitator, test-strategist, qa-triage-lead)
- Pricing and effort estimation workflow in proposal-strategist
- Communication setup section in project-shepherd (channel taxonomy, meeting templates, status reports, escalation matrix)
- Invoicing capabilities in financial-controller (invoice templates, AR aging, payment reminders)
- Contract drafting in legal-compliance-checker (NDAs, SOW terms, open-source license guidance)

### Changed
- **Renamed** `finance-tracker` -> `financial-controller` (support/) -- added Write/Edit tools, invoicing
- **Renamed** `autonomous-optimization-architect` -> `ai-cost-optimizer` (engineering/) -- narrowed to AI cost focus
- **Moved** `workflow-optimizer` from testing/ to project-management/ -- added Write/Edit tools, Lean/Six Sigma focus
- **Moved** `accounts-payable-agent` from specialized/ to support/ -- removed crypto rails, added Stripe
- **Fixed** `incident-response-commander` -- replaced PagerDuty with Alertmanager/Grafana/Loki, simplified escalation for solo founder
- **Fixed** `database-optimizer` -- added ORM awareness, IRL stack specifics, handoff contract
- **Fixed** `outbound-strategist` -- added Write tool, Deal Briefing handoff to deal-strategist
- **Fixed** `analytics-reporter` -- added cross-cutting tag for discoverability
- Cleaned emoji headers from 13 agency-import agents
- Removed `agency-import` tag from 13 customized agents
- Fixed encoding violations (U+2013, U+2014, U+2192) in 7 files

### Removed
- **Retired** `infrastructure-maintainer` (support/) -- merged useful content into infra-engineer

## [agency-1.8.0] - 2026-03-26

### Added
- **Commit guard script** (`scripts/commit_guard.py`) -- data-driven PreToolUse/PostToolUse guard that blocks commits containing files that should be gitignored (build artifacts, dependency directories, secrets, OS junk). Pattern table covers Python, Node, PHP, Ruby, Rust, Java/JVM, .NET, and General ecosystems.
  - `post` subcommand (PostToolUse): warns on stderr after `git add` if staged files match ignored patterns
  - `pre` subcommand (PreToolUse): blocks `git commit` with exit 2 if staged files match ignored patterns
  - `check` subcommand (manual): prints violations and exits 1, or reports clean and exits 0
  - `rules` subcommand: prints the active pattern table grouped by ecosystem
  - Registered `commit_guard.py pre` in PreToolUse Bash hooks (after `version_guard.py`, before `pre-deploy-secrets-sync.sh`)
  - Registered `commit_guard.py post` in PostToolUse Bash hooks (after `auto-tag.py`, before `post-deploy-secrets-verify.sh`)
  - Added `commit-guard` entry to `registry.yaml` scripts section

## [agency-1.7.0] - 2026-03-24

### Added
- **Format files hook** (`scripts/format_files.py`) -- data-driven PostToolUse formatter and PreToolUse guard for Edit/Write tools. Add new formatters or block rules by editing the RULES table -- no hook registration changes needed.
  - PostToolUse: auto-runs `terraform fmt` on `.tf` files after edits
  - PreToolUse: blocks direct edits to lock files (pnpm-lock.yaml, package-lock.json, yarn.lock, uv.lock, composer.lock, Cargo.lock, poetry.lock, Gemfile.lock)
  - Includes `rules` subcommand to print the active rule table for debugging

## [agency-1.6.0] - 2026-03-20

### Added
- **Entropy agent** (`agents/engineering/entropy.md`) -- secrets lifecycle manager that watches Bitwarden, syncs to Ansible Vault/K8s targets, enforces rotation policy, and alerts on drift
- **Secrets-sync skill** (`skills/secrets-sync/`) -- user-invocable workflow for syncing secrets from Bitwarden to infrastructure targets
- **Pre-deploy secrets sync hook** (`hooks/pre-deploy-secrets-sync.sh`) -- PreToolUse hook that triggers secret sync before deployment commands
- **Post-deploy secrets verify hook** (`hooks/post-deploy-secrets-verify.sh`) -- PostToolUse hook that verifies secrets match after deployments

### Changed
- **Orchestrator agent v2** (`agents/core/orchestrator.md`) -- major rewrite adding agent coordination patterns (parallel spawning, background agents, SendMessage continuations, worktree isolation), subagent selection tables, NEXUS integration section, hook compliance awareness, and 6th iron law ("never combine unrelated changes")
- Updated orchestrator registry description to include trigger text for subagent selection
- Updated CLAUDE.md with Entropy agent documentation and engineering division details

## [agency-1.5.0] - 2026-03-19

### Changed
- Grant Agent tool to all 148 agents for universal orchestration -- every agent can now spawn subagents and teams, enabling mesh-style self-organization instead of requiring escalation through managers

## [agency-1.4.1] - 2026-03-19

### Changed
- Grant Agent tool to all 12 managing agents, enabling delegation through the org chart hierarchy: CEO, Orchestrator, CTO, VP of Engineering, DevOps Manager, Incident Response Commander, Studio Producer, Project Shepherd, Studio Operations, Sprint Prioritizer, Sales Coach, Finance Tracker

## [agency-1.4.0] - 2026-03-19

### Added
- **Shared changelog parsing library** (`scripts/_shared/changelog.py`) -- reusable CHANGELOG.md parser following the Apache Commons shared-utilities pattern. Two public functions: `get_latest_changelog_version()` and `has_content_under_header()`.
- **Auto-tag hook** (`scripts/auto-tag.py`) -- PostToolUse hook that detects `gh pr merge` commands and automatically creates + pushes a git tag when CHANGELOG version is ahead of the latest tag. Includes `ci` subcommand for GitHub Actions.
- **Auto-tag GitHub Action** (`.github/workflows/auto-tag.yml`) -- triggers on pushes to main that touch CHANGELOG.md or plugin.json, runs `auto-tag.py ci` to create tags.
- PostToolUse hook registration in hooks.json (14 event types total)

### Changed
- Refactored all 10 scripts to use `_shared/` utility modules (git_ops, dotted, encoding, paths, audit, summon_state)

### Fixed
- `worktree_lifecycle.py` slug computation no longer incorrectly lstrips the leading slash (uses `_shared.paths.cwd_slug`)

## [agency-1.3.0] - 2026-03-18

### Added
- **Shared frontmatter config library** (`scripts/frontmatter_config.py`) -- extracts CLAUDE.md hierarchy resolution into a reusable module (idea 73). Three public functions: `resolve_config()`, `resolve_typed()`, `resolve_frontmatter()`. Deep-merge semantics with last-wins. `home_override` parameter for testing.
- **Instructions guard** (`scripts/instructions-guard.py`) -- InstructionsLoaded hook validating UTF-8 encoding and detecting [PLACEHOLDER] markers when CLAUDE.md/rules files load into context. Advisory only.
- **PostCompact recovery** (`scripts/postcompact-recovery.py`) -- PostCompact hook verifying critical context survived compaction. Checks agent persona and configurable reinject strings against compact summary. Writes audit JSONL.
- **Config tamper guard** (`scripts/config-tamper-guard.py`) -- ConfigChange hook with two-phase design: snapshots settings.json at SessionStart, diffs against cache on ConfigChange. Blocks removal of protected keys (hooks, permissions.deny) via JSON decision format.
- **Worktree lifecycle** (`scripts/worktree_lifecycle.py`) -- WorktreeCreate hook that replaces default worktree creation, propagates git hooks from main repo, checks for .env files. WorktreeRemove hook for audit logging.
- **Stop failure audit** (`scripts/stop-failure-audit.py`) -- StopFailure hook writing structured JSONL audit entries when sessions crash from API errors. Fire-and-forget.
- **Teammate gate** (`scripts/teammate-gate.py`) -- TeammateIdle/TaskCompleted hook validating subagent output. Discovers changed files via git status. Exit 2 for fixable violations (retry), continue:false for security violations (hard stop).
- **Elicitation gate** (`scripts/elicitation-gate.py`) -- Elicitation/ElicitationResult hook for MCP audit logging and optional blocking via hookSpecificOutput action:decline.
- hooks.json expanded from 3 to 13 event types (SessionStart, InstructionsLoaded, PreCompact, PostCompact, ConfigChange, WorktreeCreate, WorktreeRemove, PreToolUse, StopFailure, TeammateIdle, TaskCompleted, Elicitation, ElicitationResult)
- New frontmatter config namespaces: `enforcement`, `compaction`, `worktree`, `audit`, `mcp`
- 46 new tests across 8 test files

### Changed
- `accessibility-config.py` refactored to use shared frontmatter config library (174 -> ~60 lines, no behavior change)

## [agency-1.2.0] - 2026-03-15

### Added
- **Version guard hook** (`scripts/version_guard.py`) -- PreToolUse hook enforcing semver consistency between manifests, git tags, and CHANGELOG on protected branches. Two-tier enforcement: Tier 1 (always on) validates manifest-tag-changelog sync; Tier 2 (opt-in) uses conventional commits to compute expected versions with asymmetric comparison.
- `.version-guard.yaml` config file support for cross-repo portability
- Manifest auto-detection for package.json, pyproject.toml, Cargo.toml, composer.json, and .claude-plugin/plugin.json
- 38 tests covering all enforcement paths
- Implementation plan at `docs/plans/2026-03-15-version-guard-implementation.md`

## [agency-1.1.0] - 2026-03-15

### Added
- **ADHD accessibility skill** (`skills/accessibility-adhd/`) -- behavioral overlay that adapts Claude's communication style with 9 independently configurable behaviors: micro-chunking, reduced decisions, response brevity, momentum preservation, progress dopamine, context anchoring, anti-rabbit-hole guardrails, time awareness, and sensory-friendly formatting
- **`/init-adhd` command** (`commands/init-adhd.md`) -- guided setup wizard for configuring ADHD mode via CLAUDE.md YAML frontmatter
- **Accessibility config detector** (`scripts/accessibility-config.py`) -- parses CLAUDE.md frontmatter for auto-activation via SessionStart hook
- **User guide** (`docs/guides/accessibility-adhd.md`) -- configuration reference, behavior examples, preset recipes, and troubleshooting
- SessionStart hook for automatic ADHD mode detection from CLAUDE.md frontmatter

### Fixed
- Changelog guard now outputs errors to stderr and blocks combined `git add + commit` in a single command
- Removed explicit agent paths from `plugin.json` (uses auto-discovery)
- Fixed `marketplace.json` source path to `./` for schema compliance
- Restored `marketplace.json` for plugin discovery

## [agency-1.0.0] - 2026-03-12

### Changed
- **BREAKING**: Replaced multi-plugin structure (core, engineering, operations, research, finance) with single `infinite-room-labs@agency` plugin
- Reorganized agents into 14 division directories under `agents/` (core, engineering, design, marketing, sales, paid-media, product, project-management, testing, support, research, spatial-computing, game-development, specialized)
- Moved scripts from `plugins/core/scripts/` and `plugins/engineering/scripts/` to `scripts/`
- Moved skills from `plugins/*/skills/` to `skills/`
- Moved commands from `plugins/*/commands/` to `commands/`
- Merged hooks from multiple plugins into single `hooks/hooks.json`
- Updated `summon.py` namespace discovery from `plugins/*/` to `agents/*/` divisions
- Renamed "plugin" terminology to "division" in summon.py and related tools
- Updated `find-agent` command to scan division-based structure

### Added
- **148 specialized agents** (up from 14) across 14 business divisions
- Imported 130+ agents from Agency Agents (MIT) open-source project with IRL frontmatter
- Merged 14 overlapping agents combining IRL governance with Agency personality depth
- **NEXUS orchestration system** replacing `/devops-team`:
  - `/nexus` -- Full 7-phase pipeline for complete product lifecycle
  - `/nexus-sprint` -- Focused 2-6 week feature/MVP builds
  - `/nexus-micro` -- Lightweight 1-5 day tasks with pre-built runbooks
- `strategy/` directory with NEXUS reference material (doctrine, playbooks, runbooks, coordination templates)
- New divisions: design, marketing, sales, paid-media, product, project-management, testing, support, spatial-computing, game-development, specialized
- Core division agents: CEO (merged), Orchestrator, Reality Checker
- PreToolUse hook for changelog-guard (commit protection on protected branches)
- CONTRIBUTING.md with merged agent design guidelines
- Comprehensive README.md with full agent catalog

### Removed
- `plugins/` directory structure (replaced by flat layout)
- `.claude-plugin/marketplace.json` (replaced by single `plugin.json`)
- Individual plugin `plugin.json` files (5 files)
- `/devops-team` skill (replaced by `/nexus`)
- `plugins/operations/TODO.md` and `plugins/finance/TODO.md` (operations and finance agents now in specialized/support divisions)

## [core-0.2.0] - 2026-03-11

### Added
- **SUMMON runtime agent loading system** (`/load-agent`, `/end-agent-session`)
- `summon.py` CLI with 6 subcommands: list, discover, info, validate, state (create/check/clean/delete/reminder)
- `load-agent` skill with multi-phase flow: parse input, discovery, state check, persona injection
- `end-agent-session` skill for clean session teardown
- `load-agent` and `end-agent-session` thin-router commands
- SessionStart hook for stale state cleanup
- PreCompact hook for persona persistence after context compaction
- CLAUDE_SESSION_ID-based staleness detection with 24h TTL fallback
- Dynamic plugin namespace discovery from `plugins/*/` directories
- 35 tests covering all CLI subcommands
- 4 new entries in `registry.yaml` (2 skills, 2 commands)
