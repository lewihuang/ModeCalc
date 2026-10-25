#!/bin/bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ "$(uname -s)" != Darwin ]]; then
  echo "Build the macOS application on a Mac." >&2
  exit 1
fi
PYTHON="${MODECALC_PYTHON:-$ROOT/.venv/bin/python}"
"$PYTHON" -c 'import sys; assert sys.version_info[:2] == (3, 12), "Use Python 3.12 for release builds"'
"$PYTHON" -c 'import zlib; assert getattr(zlib, "__file__", None), "py2app 0.28.10 requires a Python framework build (python.org/Homebrew/setup-python), not a uv-managed interpreter"'
ARCH="${MODECALC_ARCH:-$("$PYTHON" -c 'import platform; print(platform.machine())')}"
case "$ARCH" in arm64|x86_64|universal2) ;; *) echo "Unsupported architecture: $ARCH" >&2; exit 1 ;; esac
export MODECALC_ARCH="$ARCH"
if [[ "$ARCH" == universal2 ]]; then
  FRAMEWORK="$("$PYTHON" -c 'import sys; print(sys.base_prefix + "/Python")')"
  lipo "$FRAMEWORK" -verify_arch arm64 x86_64
fi
# Only remove this script's generated architecture-specific directories.
rm -rf "$ROOT/build/macos-$ARCH" "$ROOT/dist/macos-$ARCH"
"$PYTHON" scripts/make_macos_icon.py
"$PYTHON" scripts/collect_macos_licenses.py
"$PYTHON" packaging/macos/setup.py py2app --bdist-base "build/macos-$ARCH" --dist-dir "dist/macos-$ARCH"
APP="$ROOT/dist/macos-$ARCH/ModeCalc.app"
"$PYTHON" scripts/thin_macos.py "$APP" "$ARCH"
"$PYTHON" scripts/verify_macos.py "$APP" "$ARCH"
"$PYTHON" scripts/sign_macos.py "$APP"
VERSION="$("$PYTHON" -c 'from app_version import VERSION; print(VERSION)')"
ZIP="$ROOT/dist/ModeCalc-v$VERSION-macos-$ARCH.zip"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
(cd "$(dirname "$ZIP")" && shasum -a 256 "$(basename "$ZIP")" > "$(basename "$ZIP").sha256")
echo "App: $APP"
echo "Archive: $ZIP"
