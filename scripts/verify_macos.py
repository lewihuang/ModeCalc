"""Reject missing assets, host-library references and incompatible Mach-O files."""

import json
import plistlib
import sys
from pathlib import Path

from macholib.MachO import MachO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_version import BUNDLE_ID

root = Path(sys.argv[1]).resolve()
arch = sys.argv[2]
required_cpus = {"arm64": {16777228}, "x86_64": {16777223},
                 "universal2": {16777228, 16777223}}[arch]
metadata = plistlib.loads((root / "Contents" / "Info.plist").read_bytes())
assert metadata["CFBundleIdentifier"] == BUNDLE_ID
assert metadata["PyRuntimeLocations"] and all(path.startswith("@executable_path/") for path in metadata["PyRuntimeLocations"]), "App depends on a host Python runtime"
for asset in ("index.html", "app.js", "style.css", "staff.js", "keyboard.js", "fretboard.js",
              "vendor/vexflow-core.js", "vendor/traste.min.js",
              "vendor/fonts/bravura/bravura.woff2", "vendor/fonts/academico/academico.woff2",
              "fonts/Quicksand-Medium.ttf"):
    assert (root / "Contents" / "Resources" / "static" / asset).is_file(), asset

count = 0
minimum = (0, 0, 0)
magic = {b"\xcf\xfa\xed\xfe", b"\xfe\xed\xfa\xcf", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
for path in root.rglob("*"):
    if path.is_symlink():
        assert path.resolve().is_relative_to(root), f"External symlink: {path}"
        continue
    if not path.is_file():
        continue
    with path.open("rb") as source:
        if source.read(4) not in magic:
            continue
    count += 1
    native = MachO(str(path))
    actual_cpus = {header.header.cputype for header in native.headers}
    assert required_cpus == actual_cpus, f"Wrong architecture for {arch}: {path}; CPU types: {actual_cpus}"
    for header in native.headers:
        if header.header.cputype not in required_cpus:
            continue
        for _, _, dependency in header.walkRelocatables():
            assert dependency.startswith(("@", "/System/Library/", "/usr/lib/")), f"Host library: {path}: {dependency}"
        for command, fields, _ in header.commands:
            if command.cmd == 0x32:  # LC_BUILD_VERSION
                version = fields.minos
            elif command.cmd == 0x24:  # LC_VERSION_MIN_MACOSX
                version = fields.version
            else:
                continue
            required = (version >> 16, (version >> 8) & 255, version & 255)
            minimum = max(minimum, required)
assert minimum <= (14, 0, 0), f"A dependency requires macOS {minimum}"
print(json.dumps({"architecture": arch, "native_binaries": count,
                  "dependency_minimum_os": minimum, "version": metadata["CFBundleShortVersionString"]}))
