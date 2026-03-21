from __future__ import annotations

import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
HOME_DIR = Path("/home/zeal8bit") if Path("/home/zeal8bit").is_dir() else SCRIPT_DIR.parent
ZOS_PATH = HOME_DIR / "Zeal-8-bit-OS"
MNT_DIR = Path("/mnt") if Path("/mnt").is_dir() else REPO_ROOT / "mnt"
ROMDISK_DIR = MNT_DIR / "romdisk"
USER_STATE_DIR = Path(os.environ.get("ZDE_USER_PATH", str(Path.home() / ".zeal8bit")))
COLLECTION_URL = "https://raw.githubusercontent.com/Zeal8bit/Zeal-Software-Collection/main/collection.yml"
