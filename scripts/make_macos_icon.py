"""Convert the largest existing ICO PNG frame to an Apple icon set."""

import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
data = (ROOT / "static" / "icon.ico").read_bytes()
count = struct.unpack_from("<H", data, 4)[0]
frames = []
for i in range(count):
    width, height, _, _, _, _, length, offset = struct.unpack_from("<BBBBHHII", data, 6 + 16 * i)
    frame = data[offset:offset + length]
    if frame.startswith(b"\x89PNG"):
        frames.append(((width or 256) * (height or 256), frame))
if not frames:
    raise SystemExit("The ICO has no PNG frame")
work = ROOT / "build" / "ModeCalc.iconset"
work.mkdir(parents=True, exist_ok=True)
source = ROOT / "build" / "ModeCalc-icon.png"
source.write_bytes(max(frames, key=lambda item: item[0])[1])
for size in (16, 32, 128, 256, 512):
    for scale in (1, 2):
        suffix = "@2x" if scale == 2 else ""
        target = work / f"icon_{size}x{size}{suffix}.png"
        subprocess.run(["sips", "-z", str(size * scale), str(size * scale), str(source), "--out", str(target)], check=True, stdout=subprocess.DEVNULL)
subprocess.run(["iconutil", "-c", "icns", str(work), "-o", str(ROOT / "build" / "ModeCalc.icns")], check=True)
