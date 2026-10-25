"""Build a self-contained Cocoa application, independent of the current cwd."""

import os
import platform
import sys
from pathlib import Path

from setuptools import setup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app_version import APP_NAME, VERSION, BUILD_NUMBER, BUNDLE_ID

if sys.platform != "darwin":
    raise SystemExit("py2app builds must run on macOS")

setup(
    name=APP_NAME,
    version=VERSION,
    app=[str(ROOT / "app.py")],
    options={"py2app": {
        "arch": os.environ.get("MODECALC_ARCH", platform.machine()),
        "alias": False,
        "semi_standalone": False,
        "argv_emulation": False,
        "no_chdir": True,
        "iconfile": str(ROOT / "build" / "ModeCalc.icns"),
        "resources": [str(ROOT / "build" / "ThirdPartyLicenses")] + [str(ROOT / name) for name in (
            "static", "LICENSE", "LICENSES", "THIRD_PARTY_NOTICES.md",
        )],
        "packages": ["webview", "rtmidi"],
        "includes": ["mido.backends.rtmidi", "webview.platforms.cocoa"],
        "excludes": ["pytest", "aiohttp", "tkinter", "PyInstaller",
                     "webview.platforms.winforms", "webview.platforms.edgechromium",
                     "webview.platforms.qt", "webview.platforms.gtk", "webview.platforms.cef"],
        "plist": {
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleIdentifier": BUNDLE_ID,
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": os.environ.get("MODECALC_BUILD_NUMBER", BUILD_NUMBER),
            "LSMinimumSystemVersion": "14.0",
            "NSHighResolutionCapable": True,
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
            "NSHumanReadableCopyright": "Copyright © 2026 ModeCalc contributors",
        },
    }},
)
