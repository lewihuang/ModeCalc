"""Read-only bundle resources and user-writable data; never depend on cwd."""

import os
import sys
import tempfile
from pathlib import Path


def resource_root() -> Path:
    if getattr(sys, "frozen", False):
        if sys.platform == "darwin" and os.environ.get("RESOURCEPATH"):
            return Path(os.environ["RESOURCEPATH"])
        if hasattr(sys, "_MEIPASS"):
            return Path(sys._MEIPASS)
    return Path(__file__).resolve().parent


def settings_path() -> Path:
    override = os.environ.get("MODECALC_SETTINGS_DIR")
    if override:
        return Path(override) / "ModeCalc" / "settings.json"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ModeCalc" / "settings.json"
    return Path(os.environ.get("APPDATA") or Path.home()) / "ModeCalc" / "settings.json"


def log_path() -> Path:
    if os.environ.get("MODECALC_LOG"):
        return Path(os.environ["MODECALC_LOG"])
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "ModeCalc" / "ModeCalc.log"
    return Path(tempfile.gettempdir()) / "ModeCalc_debug.log"
