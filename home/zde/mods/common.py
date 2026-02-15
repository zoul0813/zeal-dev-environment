from __future__ import annotations

from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
HOME_DIR = Path("/home/zeal8bit") if Path("/home/zeal8bit").is_dir() else SCRIPT_DIR.parent
MNT_DIR = Path("/mnt") if Path("/mnt").is_dir() else REPO_ROOT / "mnt"
ROMDISK_DIR = MNT_DIR / "romdisk"
USER_STATE_DIR = HOME_DIR / ".zeal8bit"

HELP_TEXT = "Help: update, deps, rebuild, activate, make, cmake, kernel, image, create, romdisk, emu[lator], playground"
