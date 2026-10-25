#!/bin/bash
set -euo pipefail
APP="${1:?Usage: notarize_macos.sh path/to/ModeCalc.app}"
: "${MODECALC_SIGN_IDENTITY:?Build with a Developer ID Application identity first}"
: "${MODECALC_NOTARY_PROFILE:?Set a notarytool keychain profile}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$(cd "$(dirname "$APP")" && pwd)/$(basename "$APP")"
PYTHON="${MODECALC_PYTHON:-$ROOT/.venv/bin/python}"
"$PYTHON" "$ROOT/scripts/sign_macos.py" "$APP"
ARCHES="$(lipo -archs "$APP/Contents/MacOS/ModeCalc")"
case "$ARCHES" in
  "x86_64 arm64"|"arm64 x86_64") ARCH=universal2 ;;
  arm64|x86_64) ARCH="$ARCHES" ;;
  *) echo "Unsupported bundle architectures: $ARCHES" >&2; exit 1 ;;
esac
VERSION="$(/usr/libexec/PlistBuddy -c 'Print CFBundleShortVersionString' "$APP/Contents/Info.plist")"
ZIP="$(dirname "$APP")/ModeCalc-v$VERSION-macos-$ARCH.zip"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
RESULT="$(dirname "$APP")/notarization-result.json"
xcrun notarytool submit "$ZIP" --keychain-profile "$MODECALC_NOTARY_PROFILE" --wait --output-format json > "$RESULT"
if ! "$PYTHON" -c 'import json,sys; result=json.load(open(sys.argv[1])); print(result); sys.exit(0 if result.get("status") == "Accepted" else 1)' "$RESULT"; then
  SUBMISSION="$("$PYTHON" -c 'import json,sys; print(json.load(open(sys.argv[1]))["id"])' "$RESULT")"
  xcrun notarytool log "$SUBMISSION" --keychain-profile "$MODECALC_NOTARY_PROFILE" || true
  exit 1
fi
xcrun stapler staple "$APP"
xcrun stapler validate "$APP"
codesign --verify --deep --strict "$APP"
spctl --assess --type execute --verbose "$APP"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"
(cd "$(dirname "$ZIP")" && shasum -a 256 "$(basename "$ZIP")" > "$(basename "$ZIP").sha256")
echo "Notarized archive: $ZIP"
