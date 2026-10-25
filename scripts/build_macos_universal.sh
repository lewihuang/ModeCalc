#!/bin/bash
# Build one app for both Intel and Apple Silicon using a dedicated environment.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
BASE_PYTHON="${MODECALC_PYTHON:-$ROOT/.venv/bin/python}"
"$BASE_PYTHON" -c 'import sys,zlib; assert sys.version_info[:2] == (3,12); assert getattr(zlib,"__file__",None), "Use a Python 3.12 framework build"'
FRAMEWORK="$("$BASE_PYTHON" -c 'import sys; print(sys.base_prefix + "/Python")')"
if ! lipo "$FRAMEWORK" -verify_arch arm64 x86_64; then
  echo "Universal 2 requires a Python framework containing arm64 and x86_64." >&2
  exit 1
fi
VENV="$ROOT/.venv-universal2"
"$BASE_PYTHON" -m venv "$VENV"
PYTHON="$VENV/bin/python"
"$PYTHON" -m pip install -r requirements.txt 'delocate==0.13.0'
WHEELS="$ROOT/build/universal2-wheels"
mkdir -p "$WHEELS/arm64" "$WHEELS/x86_64" "$WHEELS/merged"
# Keep both source wheels at the exact installed runtime version.
RTMIDI_VERSION="$("$PYTHON" -c 'from importlib.metadata import version; print(version("python-rtmidi"))')"
"$PYTHON" -m pip download --no-deps --only-binary=:all: --implementation cp --python-version 312 --abi cp312 --platform macosx_11_0_arm64 --dest "$WHEELS/arm64" "python-rtmidi==$RTMIDI_VERSION"
"$PYTHON" -m pip download --no-deps --only-binary=:all: --implementation cp --python-version 312 --abi cp312 --platform macosx_10_9_x86_64 --dest "$WHEELS/x86_64" "python-rtmidi==$RTMIDI_VERSION"
"$VENV/bin/delocate-merge" "$WHEELS/arm64/python_rtmidi-$RTMIDI_VERSION-"*.whl "$WHEELS/x86_64/python_rtmidi-$RTMIDI_VERSION-"*.whl -w "$WHEELS/merged"
"$PYTHON" -m pip install --force-reinstall --no-deps "$WHEELS/merged/python_rtmidi-$RTMIDI_VERSION-"*universal2.whl
# Ensure merged extensions can be loaded while building on Apple Silicon.
"$PYTHON" - <<'PY'
import subprocess
from importlib.metadata import distribution
dist = distribution('python-rtmidi')
for file in dist.files or []:
    if str(file).endswith('.so'):
        path = str(dist.locate_file(file))
        subprocess.run(['lipo', path, '-verify_arch', 'arm64', 'x86_64'], check=True)
        subprocess.run(['codesign', '--force', '--sign', '-', path], check=True)
PY
MODECALC_ARCH=universal2 MODECALC_PYTHON="$PYTHON" bash scripts/build_macos.sh
