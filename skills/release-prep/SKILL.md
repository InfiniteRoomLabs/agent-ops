---
name: release-prep
description: Use when preparing a new version release of a library or project
tags:
  function: [engineering]
  scenario: [release-management]
  custom: [versioning, changelog, git-tags]
---

# Release Prep

Guide a repository through a complete release cycle: version bump, CHANGELOG update, git tag, and GitHub release.

## Iron Law

**NO RELEASE WITHOUT CHANGELOG UPDATE.** If the CHANGELOG has not been updated for this version, stop and update it before proceeding.

## Prerequisite: Release Readiness Certificate

Before starting the release cycle, check for a **Release Readiness Certificate** from Reality Checker. This certificate confirms the version has passed final quality validation.

- If a certificate is present and its status is **READY FOR RELEASE**, proceed with Step 1 using the version specified in the certificate.
- If no certificate is present, ask the user whether to request one by invoking Reality Checker first. Do not block if the user explicitly opts to skip, but warn that releasing without certification bypasses the final quality gate.
- If a certificate is present but its status is **NOT READY**, stop and surface the blocking reasons. Do not proceed until the blockers are resolved and a new certificate with READY status is provided.

## Step 0: Check for Repo-Local Release Tooling

The target repo may ship its own bump/release scripts and conventions that
OVERRIDE the generic steps below. Before anything else:

1. **Read the target repo's CLAUDE.md** (it is NOT auto-loaded when the repo
   was attached via `/add-dir` -- read it explicitly) and look for a release
   or versioning section.
2. Look for bump tooling: `tools/`, `scripts/`, `bin/` entries matching
   `*version*`/`*bump*`/`*release*`, plus `mise.toml`/`Makefile`/`justfile`
   release tasks.
3. If found, use the repo's tooling for Step 4 (and any other step it
   covers) instead of hand-editing manifests. Repo convention wins.

Example: this marketplace repo itself mandates `tools/version_bump.py`
(syncs plugin.json + pyproject.toml, refreshes uv.lock) -- hand-editing
those files violates its CLAUDE.md and risks a version-guard block.

## Step 1: Detect Current Version

Read the package manifest to find the current version:

| Manifest | Version field |
|----------|--------------|
| package.json | `"version"` |
| composer.json | `"version"` |
| Cargo.toml | `version` under `[package]` |
| pyproject.toml | `version` under `[project]` or `[tool.poetry]` |
| go.mod | latest git tag (Go uses tags, not manifest versions) |

If no manifest is found, check for the latest git tag matching `v*` or a VERSION file.

Display the current version to the user.

## Step 2: Determine Release Type

Ask the user which release type to use:

| Type | When to use | Example |
|------|-------------|---------|
| **patch** (x.y.Z) | Bug fixes, documentation updates, no API changes | 1.2.3 -> 1.2.4 |
| **minor** (x.Y.0) | New features, backward-compatible additions | 1.2.3 -> 1.3.0 |
| **major** (X.0.0) | Breaking changes, API removals, incompatible changes | 1.2.3 -> 2.0.0 |

Use AskUserQuestion to get the release type. Include the current version and what the new version will be.

## Step 3: Generate CHANGELOG Entry

Gather commits since the last tag:

```
git log $(git describe --tags --abbrev=0)..HEAD --oneline --no-merges
```

Group commits into Keep a Changelog categories:

- **Added** -- new features
- **Changed** -- changes to existing functionality
- **Deprecated** -- soon-to-be removed features
- **Removed** -- removed features
- **Fixed** -- bug fixes
- **Security** -- vulnerability fixes

Present the draft CHANGELOG entry to the user for review. Use this format:

```markdown
## [X.Y.Z] - YYYY-MM-DD

### Added
- Description of addition (#PR)

### Fixed
- Description of fix (#PR)
```

Edit CHANGELOG.md to insert the new entry below `## [Unreleased]` (or at the top if no Unreleased section exists).

## Step 4: Bump Version

If Step 0 found repo-local bump tooling, use it and skip the manual edits
below. Otherwise update the version in all relevant manifest files. Common
multi-file cases:

- Node.js: `package.json` and `package-lock.json`
- Rust: `Cargo.toml` and `Cargo.lock`
- Python: `pyproject.toml` and optionally `__version__` in source
- PHP: `composer.json`

Use the Edit tool for precise replacements. Do NOT rewrite entire files.

## Step 5: Commit and Tag

Stage the changed files and create a release commit:

```
git add CHANGELOG.md {manifest files}
git commit -m "release: vX.Y.Z"
```

Create an annotated git tag:

```
git tag -a vX.Y.Z -m "Release vX.Y.Z"
```

## Step 6: Create GitHub Release

Ask the user if they want to create a GitHub release. If yes:

```
gh release create vX.Y.Z --title "vX.Y.Z" --notes-file - <<< "{changelog entry}"
```

Use the CHANGELOG entry from Step 3 as the release notes.

## Step 7: Post-Release Reminders

Remind the user about next steps based on the detected package manager:

| Manager | Publish command | Registry |
|---------|----------------|----------|
| npm | `npm publish` | npmjs.com |
| composer | Push tag (Packagist auto-detects) | packagist.org |
| cargo | `cargo publish` | crates.io |
| pip | `python -m build && twine upload dist/*` | pypi.org |

Also remind:
- Push the tag: `git push origin vX.Y.Z`
- Push the commit: `git push`
- Update any documentation sites if applicable

## Anti-Patterns

- Do NOT auto-push without user confirmation.
- Do NOT create a tag if the working directory is dirty (unstaged changes exist).
- Do NOT skip the CHANGELOG step even if the user says "just tag it."
- Do NOT use `npm version` or `cargo release` -- handle versioning manually for full control.
