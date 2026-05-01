# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!--
  EXAMPLE BLOCK -- everything from this comment to the end of the file is illustrative only.
  Delete it and replace with real release entries that describe the changes in this commit.
  Keep the five lines above (the title and the two paragraphs about Keep a Changelog and
  Semantic Versioning) exactly as they are -- those are the canonical header.

  Each release gets a `## [VERSION] - YYYY-MM-DD` heading. Group changes under the standard
  Keep a Changelog section names: Added, Changed, Deprecated, Removed, Fixed, Security.
  Omit any section that has no entries. Newest release goes on top.

  Semantic Versioning recap: MAJOR.MINOR.PATCH
    MAJOR  -- incompatible API/behavior change
    MINOR  -- backwards-compatible feature
    PATCH  -- backwards-compatible bug fix
-->

## [0.1.1] - {{DATE}}

### Fixed
- Off-by-one in the pagination cursor returned by `listItems()`.

## [0.1.0] - {{DATE}}

### Added
- Initial public release of the `widget` CLI with `create`, `list`, and `delete` commands.
- README, LICENSE, and contribution guide.

### Changed
- Default output format switched from JSON to a human-readable table; pass `--json` to restore the old format.

### Deprecated
- `--legacy-mode` flag. Will be removed in 0.2.0; use `--compat=v0` instead.

### Removed
- Dropped support for Python 3.10. Minimum is now 3.11.

### Fixed
- Crash when `~/.config/widget/config.toml` was missing instead of falling back to defaults.

### Security
- Bumped `requests` to 2.32.3 to pull in CVE-2024-35195 fix.
