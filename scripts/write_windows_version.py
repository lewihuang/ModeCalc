"""Generate Windows version values from the shared app metadata."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app_version import VERSION

target = ROOT / "version_info.txt"
source = target.read_text(encoding="utf-8")
parts = tuple(int(part) for part in VERSION.split(".")) + (0,)
source = re.sub(r"(filevers|prodvers)=\([^)]*\)", lambda match: f"{match[1]}={parts}", source)
source = re.sub(r"(u'(?:FileVersion|ProductVersion)', u')[^']*'", lambda match: match[1] + VERSION + "'", source)
target.write_text(source, encoding="utf-8")
