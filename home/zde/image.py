from __future__ import annotations

import argparse

from common import HOME_DIR, MNT_DIR
from process import run


def cmd_image(args: argparse.Namespace) -> int:
    image_type = args.image_type
    size = args.size
    image_path = MNT_DIR / f"{image_type}.img"

    if image_path.exists():
        reply = input("Image exists, overwrite? ([Y]es, [N]o) ").strip().lower()
        if reply not in {"y", "yes"}:
            return 1
        image_path.unlink()

    if image_type == "eeprom":
        size = size or "32"
    elif image_type == "cf":
        size = size or "64"
    elif image_type == "tf":
        size = size or "4096"

    return run([str(HOME_DIR / "zsync.sh"), image_type, size])
