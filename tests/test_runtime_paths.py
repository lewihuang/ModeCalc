"""Bundle and user paths must work without a writable working directory."""

import json
from pathlib import Path

import runtime_paths
import settings_store


def test_mac_paths_and_legacy_migration(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.delenv("MODECALC_SETTINGS_DIR", raising=False)
    monkeypatch.delenv("MODECALC_LOG", raising=False)
    old = tmp_path / "ModeCalc" / "settings.json"
    old.parent.mkdir()
    old.write_text(json.dumps({"version": 2, "scale_library": {"custom": ["preserved"]}}))
    target = tmp_path / "Library" / "Application Support" / "ModeCalc" / "settings.json"
    assert settings_store.default_settings_path() == target
    assert settings_store.load_settings()["scale_library"]["custom"] == ["preserved"]
    assert target.exists() and old.exists()
    target.write_text('{"version": 2, "new": true}')
    assert settings_store.load_settings() == {"version": 2, "new": True}
    assert runtime_paths.log_path() == tmp_path / "Library" / "Logs" / "ModeCalc" / "ModeCalc.log"


def test_explicit_path_does_not_migrate(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")
    old = tmp_path / "ModeCalc" / "settings.json"
    old.parent.mkdir()
    old.write_text('{"old": true}')
    assert settings_store.load_settings(tmp_path / "explicit.json") == {}


def test_windows_and_overrides(tmp_path, monkeypatch):
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32")
    monkeypatch.delenv("MODECALC_SETTINGS_DIR", raising=False)
    monkeypatch.setenv("APPDATA", str(tmp_path / "roaming"))
    assert runtime_paths.settings_path() == tmp_path / "roaming" / "ModeCalc" / "settings.json"
    monkeypatch.setenv("MODECALC_SETTINGS_DIR", str(tmp_path / "portable"))
    assert runtime_paths.settings_path() == tmp_path / "portable" / "ModeCalc" / "settings.json"
    monkeypatch.setenv("MODECALC_LOG", str(tmp_path / "log.txt"))
    assert runtime_paths.log_path() == tmp_path / "log.txt"


def test_frozen_resources_ignore_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(runtime_paths.sys, "frozen", "macosx_app", raising=False)
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")
    monkeypatch.setenv("RESOURCEPATH", str(tmp_path / "Bundle Resources"))
    assert runtime_paths.resource_root() == tmp_path / "Bundle Resources"
    monkeypatch.setattr(runtime_paths.sys, "platform", "win32")
    monkeypatch.setattr(runtime_paths.sys, "_MEIPASS", str(tmp_path / "pyinstaller"), raising=False)
    assert runtime_paths.resource_root() == tmp_path / "pyinstaller"
