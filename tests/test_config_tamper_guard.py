"""Tests for config-tamper-guard.py -- ConfigChange hook."""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path

# Register hyphenated module under its underscore alias so that
# ``from config_tamper_guard import ...`` works in test methods.
_mod = importlib.import_module("config-tamper-guard")
sys.modules["config_tamper_guard"] = _mod


class TestSnapshotCreatesCache:
    """snapshot_settings should persist settings.json content to the cache file."""

    def test_snapshot_creates_cache(self, tmp_path: Path) -> None:
        from config_tamper_guard import snapshot_settings

        settings_path = tmp_path / "settings.json"
        settings = {
            "hooks": {"SessionStart": []},
            "permissions": {"deny": ["Bash", "Write"]},
            "model": "sonnet",
        }
        settings_path.write_text(json.dumps(settings))

        cache_dir = tmp_path / "cache"
        snapshot_settings(settings_path=settings_path, cache_dir=cache_dir)

        cache_file = cache_dir / "settings-snapshot.json"
        assert cache_file.exists()
        cached = json.loads(cache_file.read_text())
        assert cached == settings


class TestDetectRemovedProtectedKey:
    """Removing a protected key should be flagged as tampered."""

    def test_detect_removed_protected_key(self) -> None:
        from config_tamper_guard import detect_tamper

        before = {
            "hooks": {"SessionStart": []},
            "permissions": {"deny": ["Bash"]},
        }
        after = {
            "permissions": {"deny": ["Bash"]},
        }
        result = detect_tamper(before, after, protected_keys=["hooks", "permissions.deny"])
        assert result["tampered"] is True
        assert any("hooks" in r for r in result["reasons"])


class TestNoTamperWhenKeysPresent:
    """Keys present (even with modified values) should not trigger tamper detection."""

    def test_no_tamper_when_keys_present(self) -> None:
        from config_tamper_guard import detect_tamper

        before = {
            "hooks": {"SessionStart": []},
            "permissions": {"deny": ["Bash"]},
        }
        after = {
            "hooks": {"SessionStart": [], "PreCompact": []},
            "permissions": {"deny": ["Bash", "Write"]},
        }
        result = detect_tamper(before, after, protected_keys=["hooks", "permissions.deny"])
        assert result["tampered"] is False
        assert result["reasons"] == []


class TestDetectWeakenedDenyList:
    """Removing items from a list value should be flagged as weakened."""

    def test_detect_weakened_deny_list(self) -> None:
        from config_tamper_guard import detect_tamper

        before = {
            "permissions": {"deny": ["Bash", "Write", "Edit"]},
        }
        after = {
            "permissions": {"deny": ["Bash"]},
        }
        result = detect_tamper(before, after, protected_keys=["permissions.deny"])
        assert result["tampered"] is True
        assert any("permissions.deny" in r for r in result["reasons"])


class TestNoTamperOnUnprotectedChanges:
    """Changing unprotected keys should not trigger tamper detection."""

    def test_no_tamper_on_unprotected_changes(self) -> None:
        from config_tamper_guard import detect_tamper

        before = {
            "hooks": {"SessionStart": []},
            "permissions": {"deny": ["Bash"]},
            "model": "sonnet",
        }
        after = {
            "hooks": {"SessionStart": []},
            "permissions": {"deny": ["Bash"]},
            "model": "opus",
            "newKey": "newValue",
        }
        result = detect_tamper(before, after, protected_keys=["hooks", "permissions.deny"])
        assert result["tampered"] is False
        assert result["reasons"] == []
