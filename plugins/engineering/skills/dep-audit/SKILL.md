---
name: dep-audit
description: Use when auditing project dependencies for license, security, or staleness issues
tags:
  function: [engineering]
  scenario: [dependency-management]
  custom: [licenses, security, audit]
---

# Dependency Audit

Audit project dependencies for license compatibility, outdated versions, and known vulnerabilities.

## Iron Law

**FLAG ALL COPYLEFT LICENSES IN PERMISSIVE PROJECTS.** If the project uses MIT/Apache/BSD, any dependency using GPL/AGPL/LGPL/MPL must be explicitly flagged as a compatibility risk.

## Step 1: Detect Package Manager

Scan the repo root for manifest files to determine the ecosystem:

| File | Ecosystem | Lock file |
|------|-----------|-----------|
| package.json | npm/Node.js | package-lock.json, yarn.lock, pnpm-lock.yaml |
| composer.json | Composer/PHP | composer.lock |
| Cargo.toml | Cargo/Rust | Cargo.lock |
| pyproject.toml / requirements.txt | pip/Python | requirements.txt, poetry.lock |
| go.mod | Go modules | go.sum |
| Gemfile | Bundler/Ruby | Gemfile.lock |

If multiple ecosystems are detected, audit each one separately.

## Step 2: Detect Project License

Read the LICENSE file or the `license` field in the package manifest to determine the project's own license. This is needed for compatibility analysis in Step 4.

## Step 3: Check for Outdated Dependencies

Run the appropriate command for the detected package manager:

| Ecosystem | Command |
|-----------|---------|
| npm | `npm outdated --json` |
| Composer | `composer outdated --format=json` |
| Cargo | `cargo outdated --format json` (if cargo-outdated is installed, otherwise parse Cargo.toml manually) |
| pip | `pip list --outdated --format=json` |
| Go | `go list -m -u all` |
| Bundler | `bundle outdated --parseable` |

If the command is unavailable, fall back to reading the lock file and comparing versions via the registry API.

## Step 4: Identify Dependency Licenses

Determine licenses for each dependency:

| Ecosystem | Method |
|-----------|--------|
| npm | `npm ls --json` then check each package's package.json `license` field |
| Composer | `composer licenses --format=json` |
| Cargo | `cargo license` (if cargo-license is installed) or parse Cargo.toml of each dep |
| pip | `pip-licenses --format=json` (if installed) or check PyPI metadata |
| Go | Check LICENSE files in module cache or go-licenses tool |

### License Compatibility Matrix

When the project license is permissive (MIT, Apache-2.0, BSD):

| Dependency License | Status |
|-------------------|--------|
| MIT, ISC, BSD, Apache-2.0, Unlicense, CC0 | COMPATIBLE |
| LGPL-2.1, LGPL-3.0 | CAUTION -- compatible if dynamically linked |
| GPL-2.0, GPL-3.0, AGPL-3.0 | INCOMPATIBLE -- copyleft infection risk |
| MPL-2.0 | CAUTION -- file-level copyleft |
| Unknown / No license | RISK -- treat as proprietary |

## Step 5: Check for Known Vulnerabilities

Run the appropriate audit command:

| Ecosystem | Command |
|-----------|---------|
| npm | `npm audit --json` |
| Composer | `composer audit --format=json` |
| Cargo | `cargo audit --json` (if cargo-audit is installed) |
| pip | `pip-audit --format=json` (if installed) |
| Go | `govulncheck ./...` (if installed) |

If the tool is unavailable, note it as SKIPPED in the report.

## Output Format

Present the report as:

```
# Dependency Audit Report

**Project**: {name}
**Project License**: {license}
**Ecosystem**: {ecosystem}
**Total Dependencies**: {count}
**Audited**: {date}

## Summary

| Category | Count |
|----------|-------|
| Up to date | X |
| Outdated (minor) | X |
| Outdated (major) | X |
| Vulnerable | X |
| License incompatible | X |
| License caution | X |

## Vulnerabilities

| Package | Installed | Severity | Advisory | Fix |
|---------|-----------|----------|----------|-----|
| {name} | {version} | CRITICAL/HIGH/MEDIUM/LOW | {CVE or advisory ID} | Upgrade to {version} |

## License Issues

| Package | Version | License | Status | Risk |
|---------|---------|---------|--------|------|
| {name} | {version} | {license} | INCOMPATIBLE/CAUTION/RISK | {explanation} |

## Outdated Dependencies

| Package | Current | Latest | Type |
|---------|---------|--------|------|
| {name} | {current} | {latest} | major/minor/patch |

## Recommendations

1. **[CRITICAL]** {action} -- {why}
2. **[IMPORTANT]** {action} -- {why}
3. **[MAINTENANCE]** {action} -- {why}
```

## Anti-Patterns

- Do NOT install dependencies or modify lock files. Read-only analysis.
- Do NOT run `npm install`, `composer install`, etc. Work with what is already installed or use registry APIs.
- Do NOT assume all commands are available. Check first and gracefully skip unavailable tools.
- Do NOT report patch-level outdated dependencies as urgent. Focus on major version gaps and security issues.
- Do NOT conflate "outdated" with "vulnerable." Outdated is maintenance; vulnerable is security.
