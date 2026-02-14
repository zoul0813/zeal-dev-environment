from __future__ import annotations

from common import HOME_DIR, MNT_DIR, dispatch_subcommand
from process import run


def run_image(args: list[str]) -> int:
    if len(args) < 1:
        print("Usage: zde image <eeprom|cf|tf> [size]")
        return 1

    image_type = args[0]
    if image_type not in {"eeprom", "cf", "tf"}:
        print("Invalid arguments, must provide TYPE (eeprom, cf, tf)")
        return 1

    size = args[1] if len(args) > 1 else None
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


SUBCOMMANDS = {
    "run": run_image,
}


def main(args: list[str]) -> int:
    return dispatch_subcommand("image", args, SUBCOMMANDS, default="run")
