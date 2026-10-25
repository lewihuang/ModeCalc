"""Sign native code inside-out; default to a local ad-hoc identity."""

import os
import subprocess
import sys
from pathlib import Path

app = Path(sys.argv[1]).resolve()
if app.suffix != ".app" or not (app / "Contents" / "MacOS").is_dir():
    raise SystemExit("Expected a macOS .app bundle")
identity = os.environ.get("MODECALC_SIGN_IDENTITY", "-")
entitlements = Path(__file__).resolve().parents[1] / "packaging" / "macos" / "entitlements.plist"
magic = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}


def sign(path, executable=False):
    command = ["codesign", "--force", "--sign", identity]
    if identity != "-":
        command += ["--timestamp", "--options", "runtime"]
    if executable:
        command += ["--entitlements", str(entitlements)]
    subprocess.run(command + [str(path)], check=True)


for path in sorted(app.rglob("*")):
    if path.is_file() and not path.is_symlink():
        with path.open("rb") as source:
            native = source.read(4) in magic
        if native:
            sign(path, path.parent == app / "Contents" / "MacOS")
for path in sorted(app.rglob("*.framework"), key=lambda p: len(p.parts), reverse=True):
    sign(path)
sign(app, True)
subprocess.run(["codesign", "--verify", "--deep", "--strict", str(app)], check=True)
