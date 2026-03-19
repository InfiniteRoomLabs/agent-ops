"""Tests for the shared frontmatter config library."""

from __future__ import annotations

from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# parse_frontmatter tests
# ---------------------------------------------------------------------------


class TestParseFrontmatter:
    """Tests for extracting YAML frontmatter from markdown content."""

    def test_valid_frontmatter(self) -> None:
        from frontmatter_config import parse_frontmatter

        content = "---\nfoo: bar\nbaz: 42\n---\n# Hello\n"
        result = parse_frontmatter(content)
        assert result == {"foo": "bar", "baz": 42}

    def test_no_frontmatter(self) -> None:
        from frontmatter_config import parse_frontmatter

        content = "# Just a heading\nSome text.\n"
        result = parse_frontmatter(content)
        assert result is None

    def test_invalid_yaml(self) -> None:
        from frontmatter_config import parse_frontmatter

        content = "---\n: : : not valid yaml [[\n---\n# Body\n"
        result = parse_frontmatter(content)
        assert result is None

    def test_nested_frontmatter(self) -> None:
        from frontmatter_config import parse_frontmatter

        content = "---\nenforcement:\n  encoding: true\n  hooks:\n    pre_commit: true\n---\n# Doc\n"
        result = parse_frontmatter(content)
        assert result == {
            "enforcement": {
                "encoding": True,
                "hooks": {"pre_commit": True},
            }
        }


# ---------------------------------------------------------------------------
# resolve_frontmatter / resolve_config tests
# ---------------------------------------------------------------------------


class TestResolveHierarchy:
    """Tests for CLAUDE.md hierarchy merging and namespace extraction."""

    def test_hierarchy_merge(self, tmp_path: Path) -> None:
        from frontmatter_config import resolve_frontmatter

        # Global CLAUDE.md
        global_dir = tmp_path / ".claude"
        global_dir.mkdir()
        (global_dir / "CLAUDE.md").write_text(
            "---\nenforcement:\n  encoding: true\n  placeholder_check: false\n---\n# Global\n"
        )

        # Project CLAUDE.md
        project = tmp_path / "projects" / "myapp"
        project.mkdir(parents=True)
        (project / "CLAUDE.md").write_text(
            "---\nenforcement:\n  placeholder_check: true\ncustom: value\n---\n# Project\n"
        )

        result = resolve_frontmatter(cwd=project, home_override=tmp_path)
        # Project overrides global for placeholder_check, global encoding preserved
        assert result["enforcement"]["encoding"] is True
        assert result["enforcement"]["placeholder_check"] is True
        assert result["custom"] == "value"

    def test_namespace_extraction(self, tmp_path: Path) -> None:
        from frontmatter_config import resolve_config

        global_dir = tmp_path / ".claude"
        global_dir.mkdir()
        (global_dir / "CLAUDE.md").write_text(
            "---\nenforcement:\n  encoding: true\nother: stuff\n---\n# Global\n"
        )

        result = resolve_config(
            namespace="enforcement", cwd=tmp_path, home_override=tmp_path
        )
        assert result == {"encoding": True}

    def test_missing_namespace(self, tmp_path: Path) -> None:
        from frontmatter_config import resolve_config

        global_dir = tmp_path / ".claude"
        global_dir.mkdir()
        (global_dir / "CLAUDE.md").write_text(
            "---\nfoo: bar\n---\n# Global\n"
        )

        result = resolve_config(
            namespace="nonexistent", cwd=tmp_path, home_override=tmp_path
        )
        assert result == {}


# ---------------------------------------------------------------------------
# resolve_typed tests
# ---------------------------------------------------------------------------


class TestResolveTyped:
    """Tests for Pydantic model validation via resolve_typed."""

    def test_model_return(self, tmp_path: Path) -> None:
        from pydantic import BaseModel, Field

        from frontmatter_config import resolve_typed

        class EnforcementConfig(BaseModel):
            encoding: bool = True
            placeholder_check: bool = True
            protected_settings: list[str] = Field(
                default_factory=lambda: ["hooks", "permissions.deny"]
            )

        global_dir = tmp_path / ".claude"
        global_dir.mkdir()
        (global_dir / "CLAUDE.md").write_text(
            "---\nenforcement:\n  encoding: false\n  protected_settings:\n    - hooks\n---\n# Global\n"
        )

        result = resolve_typed(
            model=EnforcementConfig,
            namespace="enforcement",
            cwd=tmp_path,
            home_override=tmp_path,
        )
        assert isinstance(result, EnforcementConfig)
        assert result.encoding is False
        assert result.placeholder_check is True  # default
        assert result.protected_settings == ["hooks"]

    def test_defaults_on_missing_namespace(self, tmp_path: Path) -> None:
        from pydantic import BaseModel, Field

        from frontmatter_config import resolve_typed

        class EnforcementConfig(BaseModel):
            encoding: bool = True
            placeholder_check: bool = True
            protected_settings: list[str] = Field(
                default_factory=lambda: ["hooks", "permissions.deny"]
            )

        global_dir = tmp_path / ".claude"
        global_dir.mkdir()
        (global_dir / "CLAUDE.md").write_text(
            "---\nfoo: bar\n---\n# Global\n"
        )

        result = resolve_typed(
            model=EnforcementConfig,
            namespace="enforcement",
            cwd=tmp_path,
            home_override=tmp_path,
        )
        assert isinstance(result, EnforcementConfig)
        assert result.encoding is True
        assert result.placeholder_check is True
        assert result.protected_settings == ["hooks", "permissions.deny"]


# ---------------------------------------------------------------------------
# Edge case tests
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Edge cases for deep merge, missing files, and permissions."""

    def test_deep_merge_nested_dicts(self) -> None:
        from frontmatter_config import _deep_merge

        base = {"a": {"x": 1, "y": 2}, "b": 10}
        override = {"a": {"y": 99, "z": 3}, "c": 20}
        result = _deep_merge(base, override)
        assert result == {"a": {"x": 1, "y": 99, "z": 3}, "b": 10, "c": 20}

    def test_deep_merge_replaces_non_dict(self) -> None:
        from frontmatter_config import _deep_merge

        base = {"a": "string_value", "b": {"nested": True}}
        override = {"a": {"now": "a dict"}, "b": "now_a_string"}
        result = _deep_merge(base, override)
        assert result == {"a": {"now": "a dict"}, "b": "now_a_string"}

    def test_no_claude_md(self, tmp_path: Path) -> None:
        from frontmatter_config import resolve_frontmatter

        # No CLAUDE.md files at all
        project = tmp_path / "empty_project"
        project.mkdir()
        result = resolve_frontmatter(cwd=project, home_override=tmp_path)
        assert result == {}

    def test_skip_unreadable_files(self, tmp_path: Path) -> None:
        from frontmatter_config import resolve_frontmatter

        global_dir = tmp_path / ".claude"
        global_dir.mkdir()
        unreadable = global_dir / "CLAUDE.md"
        unreadable.write_text("---\nfoo: bar\n---\n# Global\n")
        unreadable.chmod(0o000)

        project = tmp_path / "project"
        project.mkdir()
        (project / "CLAUDE.md").write_text(
            "---\nbaz: qux\n---\n# Project\n"
        )

        result = resolve_frontmatter(cwd=project, home_override=tmp_path)
        # Should skip the unreadable global file and still return project data
        assert result == {"baz": "qux"}

        # Restore permissions for cleanup
        unreadable.chmod(0o644)
