"""Tests for config-tamper-guard.py -- ConfigChange hook."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

import pytest

# Register hyphenated module under its underscore alias so that
# ``from config_tamper_guard import ...`` works in test methods.
_mod = importlib.import_module("config-tamper-guard")
sys.modules["config_tamper_guard"] = _mod

from config_tamper_guard import (  # noqa: E402
    ConfigChangePayload,
    EnforcementConfig,
    detect_tamper,
    evaluate_change,
    find_weakenings,
    snapshot_path,
    snapshot_settings,
)


# ---------------------------------------------------------------------------
# snapshot_settings
# ---------------------------------------------------------------------------


class TestSnapshotPerSource:
    """snapshot_settings caches each existing source under its own file."""

    def test_snapshots_project_and_local(self, tmp_path: Path, monkeypatch) -> None:
        claude_dir = tmp_path / ".claude"
        claude_dir.mkdir()
        project = {"hooks": {"SessionStart": []}}
        local = {"permissions": {"deny": ["WebFetch"]}}
        (claude_dir / "settings.json").write_text(json.dumps(project))
        (claude_dir / "settings.local.json").write_text(json.dumps(local))
        # Keep user_settings out of the picture
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "nohome")

        cache_dir = tmp_path / "cache"
        snapshot_settings(cwd=tmp_path, cache_dir=cache_dir)

        assert json.loads(
            snapshot_path(cache_dir, "project_settings").read_text()
        ) == project
        assert json.loads(
            snapshot_path(cache_dir, "local_settings").read_text()
        ) == local
        assert not snapshot_path(cache_dir, "user_settings").exists()

    def test_missing_sources_skipped(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "nohome")
        cache_dir = tmp_path / "cache"
        snapshot_settings(cwd=tmp_path, cache_dir=cache_dir)
        assert list(cache_dir.iterdir()) == []

    def test_legacy_combined_snapshot_removed(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """The pre-rework single-file snapshot is cleaned up at SessionStart."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "nohome")
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        legacy = cache_dir / "settings-snapshot.json"
        legacy.write_text("{}")
        snapshot_settings(cwd=tmp_path, cache_dir=cache_dir)
        assert not legacy.exists()


# ---------------------------------------------------------------------------
# find_weakenings (recursive diff)
# ---------------------------------------------------------------------------


class TestFindWeakenings:
    def test_nested_hook_entry_removed(self) -> None:
        """Gutting hooks.PreToolUse is detected even though 'hooks' survives."""
        old = {"PreToolUse": [{"matcher": "Bash", "hooks": [{"command": "guard"}]}]}
        new = {"PreToolUse": []}
        reasons = find_weakenings(old, new, "hooks")
        assert reasons and "hooks.PreToolUse" in reasons[0]

    def test_list_of_dicts_no_typeerror(self) -> None:
        """Unhashable list items must not crash the diff (old set() bug)."""
        old = [{"matcher": "Bash"}, {"matcher": "Write"}]
        new = [{"matcher": "Bash"}]
        reasons = find_weakenings(old, new, "hooks.PreToolUse")
        assert len(reasons) == 1

    def test_scalar_modification_flagged(self) -> None:
        """Swapping a guard command for a noop is tampering, not an edit."""
        old = {"command": "uv run guard.py hook"}
        new = {"command": "true"}
        reasons = find_weakenings(old, new, "hooks.x")
        assert reasons and "modified" in reasons[0]

    def test_additions_allowed(self) -> None:
        old = {"PreToolUse": [{"matcher": "Bash"}]}
        new = {"PreToolUse": [{"matcher": "Bash"}, {"matcher": "Write"}], "Stop": []}
        assert find_weakenings(old, new, "hooks") == []

    def test_list_reorder_allowed(self) -> None:
        assert find_weakenings(["a", "b"], ["b", "a"], "permissions.deny") == []


# ---------------------------------------------------------------------------
# detect_tamper
# ---------------------------------------------------------------------------


class TestDetectRemovedProtectedKey:
    def test_detect_removed_protected_key(self) -> None:
        before = {"hooks": {"SessionStart": []}, "permissions": {"deny": ["Bash"]}}
        after = {"permissions": {"deny": ["Bash"]}}
        reasons = detect_tamper(before, after, ["hooks", "permissions.deny"])
        assert reasons and any("hooks" in r for r in reasons)


class TestNoTamperOnAdditions:
    def test_added_hooks_and_deny_items_allowed(self) -> None:
        before = {"hooks": {"SessionStart": []}, "permissions": {"deny": ["Bash"]}}
        after = {
            "hooks": {"SessionStart": [], "PreCompact": []},
            "permissions": {"deny": ["Bash", "Write"]},
        }
        assert detect_tamper(before, after, ["hooks", "permissions.deny"]) == []


class TestDetectWeakenedDenyList:
    def test_detect_weakened_deny_list(self) -> None:
        before = {"permissions": {"deny": ["Bash", "Write", "Edit"]}}
        after = {"permissions": {"deny": ["Bash"]}}
        reasons = detect_tamper(before, after, ["permissions.deny"])
        assert reasons and any("permissions.deny" in r for r in reasons)


class TestNoTamperOnUnprotectedChanges:
    def test_no_tamper_on_unprotected_changes(self) -> None:
        before = {"hooks": {"SessionStart": []}, "model": "sonnet"}
        after = {"hooks": {"SessionStart": []}, "model": "opus", "newKey": "x"}
        assert detect_tamper(before, after, ["hooks", "permissions.deny"]) == []


class TestBlockedKeyAdditions:
    def test_disable_all_hooks_flip_blocked(self) -> None:
        reasons = detect_tamper(
            {}, {"disableAllHooks": True}, [], blocked_keys=["disableAllHooks"]
        )
        assert reasons and "disableAllHooks" in reasons[0]

    def test_already_true_not_reflagged(self) -> None:
        assert detect_tamper(
            {"disableAllHooks": True},
            {"disableAllHooks": True},
            [],
            blocked_keys=["disableAllHooks"],
        ) == []


# ---------------------------------------------------------------------------
# evaluate_change (per-source snapshots, file-content reads, block semantics)
# ---------------------------------------------------------------------------


def _payload(file_path: Path, source: str = "project_settings") -> ConfigChangePayload:
    return ConfigChangePayload(config_source=source, file_path=str(file_path))


@pytest.fixture()
def env(tmp_path: Path):
    """A settings file + cache dir with a snapshot baseline."""
    settings = tmp_path / "settings.json"
    cache = tmp_path / "cache"
    cache.mkdir()
    baseline = {"hooks": {"PreToolUse": [{"matcher": "Bash"}]}}
    snapshot_path(cache, "project_settings").write_text(json.dumps(baseline))
    settings.write_text(json.dumps(baseline))
    return settings, cache, baseline


class TestEvaluateChange:
    def test_reads_content_from_file_not_payload(self, env) -> None:
        """The envelope carries no settings -- content must come from disk."""
        settings, cache, _ = env
        settings.write_text(json.dumps({"hooks": {}}))  # gutted on disk
        allowed, reason = evaluate_change(
            _payload(settings), EnforcementConfig(), cache
        )
        assert allowed is False
        assert "PreToolUse" in reason

    def test_block_does_not_advance_snapshot(self, env) -> None:
        """After a block, the baseline must still be the pre-tamper state."""
        settings, cache, baseline = env
        settings.write_text(json.dumps({}))
        allowed, _ = evaluate_change(_payload(settings), EnforcementConfig(), cache)
        assert allowed is False
        snap = json.loads(snapshot_path(cache, "project_settings").read_text())
        assert snap == baseline  # not blinded by the blocked change

    def test_allow_advances_snapshot(self, env) -> None:
        settings, cache, _ = env
        grown = {"hooks": {"PreToolUse": [{"matcher": "Bash"}], "Stop": []}}
        settings.write_text(json.dumps(grown))
        allowed, _ = evaluate_change(_payload(settings), EnforcementConfig(), cache)
        assert allowed is True
        snap = json.loads(snapshot_path(cache, "project_settings").read_text())
        assert snap == grown

    def test_sources_judged_independently(self, env) -> None:
        """A local-settings change diffs against ITS baseline, not project's."""
        settings, cache, _ = env
        local = settings.parent / "settings.local.json"
        local.write_text(json.dumps({"model": "opus"}))
        allowed, _ = evaluate_change(
            _payload(local, source="local_settings"), EnforcementConfig(), cache
        )
        assert allowed is True  # first baseline for local, no false diff

    def test_first_baseline_blocked_key_still_caught(self, tmp_path: Path) -> None:
        """A brand-new file flipping a kill-switch must not slip in as baseline."""
        cache = tmp_path / "cache"
        cache.mkdir()
        newfile = tmp_path / "settings.local.json"
        newfile.write_text(json.dumps({"disableAllHooks": True}))
        allowed, reason = evaluate_change(
            _payload(newfile, source="local_settings"), EnforcementConfig(), cache
        )
        assert allowed is False
        assert "disableAllHooks" in reason

    def test_deleted_file_is_removal(self, env) -> None:
        settings, cache, _ = env
        settings.unlink()
        allowed, reason = evaluate_change(
            _payload(settings), EnforcementConfig(), cache
        )
        assert allowed is False
        assert "hooks" in reason

    def test_invalid_json_raises_for_fail_closed(self, env) -> None:
        settings, cache, _ = env
        settings.write_text("{not json")
        with pytest.raises(json.JSONDecodeError):
            evaluate_change(_payload(settings), EnforcementConfig(), cache)
