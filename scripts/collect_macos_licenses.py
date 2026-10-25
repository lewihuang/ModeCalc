"""Copy runtime wheel license files and metadata into the standalone bundle."""

import shutil
import sysconfig
from importlib.metadata import distribution
from pathlib import Path

from packaging.requirements import Requirement

root = Path(__file__).resolve().parents[1] / "build" / "ThirdPartyLicenses"
root.mkdir(parents=True, exist_ok=True)
pending = ["mido", "python-rtmidi", "pywebview"]
seen = set()
while pending:
    name = pending.pop()
    dist = distribution(name)
    key = dist.metadata["Name"]
    if key in seen:
        continue
    seen.add(key)
    target = root / key
    target.mkdir(exist_ok=True)
    (target / "METADATA.txt").write_text(dist.read_text("METADATA") or "", encoding="utf-8")
    for file in dist.files or []:
        path = Path(str(file))
        if path.name.upper().startswith(("LICENSE", "COPYING", "COPYRIGHT")) and path.suffix.lower() in ("", ".txt", ".md", ".rst"):
            source = Path(dist.locate_file(file))
            if source.is_file():
                shutil.copy2(source, target / source.name)
    for spec in dist.requires or []:
        requirement = Requirement(spec)
        if requirement.marker is None or requirement.marker.evaluate():
            pending.append(requirement.name)
python_license = Path(sysconfig.get_path("stdlib")) / "LICENSE.txt"
if python_license.is_file():
    shutil.copy2(python_license, root / "Python-LICENSE.txt")
