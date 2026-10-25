"""Remove unused architecture slices before signing a single-architecture app."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

from macholib.MachO import MachO

root = Path(sys.argv[1]).resolve()
arch = sys.argv[2]
if root.suffix != ".app" or not (root / "Contents/MacOS").is_dir():
    raise SystemExit(f"Expected an application bundle: {root}")
if arch == "universal2":
    raise SystemExit(0)
cpu = {"arm64": 16777228, "x86_64": 16777223}[arch]
magic = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
count = 0
for path in root.rglob("*"):
    if path.is_symlink() or not path.is_file():
        continue
    with path.open("rb") as source:
        if source.read(4) not in magic:
            continue
    native = MachO(str(path))
    assert any(header.header.cputype == cpu for header in native.headers), f"Missing {arch}: {path}"
    if len(native.headers) > 1:
        temporary = path.with_name(path.name + ".thin")
        try:
            subprocess.run(["lipo", str(path), "-thin", arch, "-output", str(temporary)], check=True)
            shutil.copystat(path, temporary)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        count += 1
print(f"Removed unused architecture slices from {count} native files ({arch}).")
