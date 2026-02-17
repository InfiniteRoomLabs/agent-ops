---
name: publish-package
description: Use when publishing a package to a registry (npm, packagist, PyPI, crates.io)
allowed-tools: Bash(npm:*), Bash(cargo:*), Bash(pip:*), Bash(composer:*), Bash(gh:*), Bash(git:*), Read, Glob
tags:
  function: [engineering]
  scenario: [release-management]
  custom: [publishing, npm, packagist, pypi]
---

# Publish Package

Guided workflow for publishing a package to its registry. Enforces pre-publish checks before executing.

## Iron Law

**NO PUBLISH WITHOUT PASSING TESTS.** If tests fail or no test suite exists, stop and resolve before publishing.

## Step 1: Detect Package Type

Scan the repo root for a package manifest:

| File | Registry | Publish command |
|------|----------|----------------|
| package.json | npm | `npm publish` |
| composer.json | Packagist | Push tag (auto-detected by Packagist) |
| Cargo.toml | crates.io | `cargo publish` |
| pyproject.toml | PyPI | `python -m build && twine upload dist/*` |
| setup.py | PyPI | `python -m build && twine upload dist/*` |

If no manifest is found, abort with a clear message.

## Step 2: Pre-Publish Verification

Run each check. All must pass before proceeding.

### 2a. Clean Working Directory

```
git status --porcelain
```

If output is non-empty, abort: "Working directory has uncommitted changes. Commit or stash before publishing."

### 2b. Correct Branch

```
git branch --show-current
```

Must be on `main`, `master`, or a branch matching `release/*`. If not, warn the user and ask for confirmation.

### 2c. Tests Pass

Run the test suite for the detected ecosystem:

| Ecosystem | Command |
|-----------|---------|
| npm | `npm test` |
| Composer | `composer test` or `./vendor/bin/phpunit` |
| Cargo | `cargo test` |
| Python | `pytest` or `python -m pytest` |

If tests fail, stop immediately. Display the failure output and do not continue.

### 2d. Version Bumped

Read the current version from the manifest. Read the latest git tag:

```
git describe --tags --abbrev=0
```

If the manifest version matches the latest tag, the version has NOT been bumped. Abort: "Version has not been bumped since the last release. Run release-prep first."

## Step 3: Pre-Publish Checklist

Verify these files exist and warn if missing:

- [ ] README.md -- registries display this as the package page
- [ ] LICENSE -- required by most registries
- [ ] .npmignore (npm) / .gitattributes with `export-ignore` (Composer) / MANIFEST.in (Python) -- prevents publishing unnecessary files

For npm specifically, also check:
- [ ] `"files"` field in package.json, or `.npmignore` exists
- [ ] `"main"` or `"exports"` field points to an existing file

Present the checklist results. If any items are missing, warn but allow the user to proceed.

## Step 4: Publish

Execute the publish command for the detected ecosystem.

### npm
```
npm publish
```

If the package is scoped (`@scope/name`), ask if it should be public:
```
npm publish --access public
```

### Composer / Packagist
Packagist auto-detects from git tags. Verify the tag exists:
```
git tag -l "v*" --sort=-v:refname | head -1
```

If no tag matches the current version, create one:
```
git tag -a vX.Y.Z -m "Release vX.Y.Z"
git push origin vX.Y.Z
```

### Cargo
```
cargo publish
```

If it is a workspace with multiple crates, ask which crate to publish:
```
cargo publish -p {crate-name}
```

### Python
```
python -m build
twine upload dist/*
```

## Step 5: Post-Publish

### Create GitHub Release (if not already done)

Check if a GitHub release exists for this version:
```
gh release view vX.Y.Z
```

If not, create one:
```
gh release create vX.Y.Z --title "vX.Y.Z" --generate-notes
```

### Verify Publication

For npm:
```
npm view {package-name} version
```

For crates.io:
```
cargo search {crate-name}
```

Report success with the registry URL where the package can be found.

## Anti-Patterns

- Do NOT publish if tests have not been run in this session. Always run them fresh.
- Do NOT skip the version bump check. Publishing the same version twice will fail or cause confusion.
- Do NOT use `--force` flags on publish commands.
- Do NOT publish from a dirty working directory.
- Do NOT auto-publish without user confirmation at the final step.
