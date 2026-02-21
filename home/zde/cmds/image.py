from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from mods.common import HOME_DIR, MNT_DIR
from mods.process import run
from mods.requirements import require_deps
from mods.tui.contract import ActionSpec, CommandSpec

def _pack_cf_image() -> int:
    pack_script = HOME_DIR / "Zeal-8-bit-OS" / "tools" / "pack.py"
    cf_dir = MNT_DIR / "cf"
    image = MNT_DIR / "cf.img"
    return run([sys.executable, str(pack_script), str(image), str(cf_dir)])


def _build_zealfs_image(image_type: str, size: str) -> int:
    image = MNT_DIR / f"{image_type}.img"
    mount_dir = MNT_DIR / image_type
    zealfs_bin = HOME_DIR / "ZealFS" / "build" / "zealfs"
    media_dir = "/media/zealfs"
    cmd = [
        "sudo",
        str(zealfs_bin),
        "-v2",
        f"--image={image}",
        f"--size={size}",
    ]
    if image_type == "tf":
        cmd.append("--mbr")
    cmd.append(media_dir)

    rc = run(cmd)
    if rc != 0:
        return rc
    rc = run(
        [
            "sudo",
            "rsync",
            "-ruLkv",
            "--temp-dir=/tmp",
            "--no-perms",
            "--whole-file",
            "--delete",
            f"{mount_dir}/",
            f"{media_dir}/",
        ]
    )
    if rc != 0:
        return rc
    return run(["sudo", "umount", media_dir])


def _copy_path_to_image(path: Path, image_type: str) -> None:
    mount_dir = MNT_DIR / image_type
    if not path.exists():
        print(f"Warning: '{path}' does not exist, skipping")
        return

    mount_dir.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        print(f"  Copying file: {path}")
        shutil.copy2(path, mount_dir / path.name)
        return

    if path.is_dir():
        print(f"  Copying directory contents (top-level files only): {path}")
        for child in path.iterdir():
            if child.is_file():
                shutil.copy2(child, mount_dir / child.name)
        return

    print(f"Warning: '{path}' is not a file or directory, skipping")


def _subcmd_add(image_type: str, args: list[str]) -> int:
    if not args:
        print("Error: No paths provided")
        print(f"Usage: zde image {image_type} add <path1> [path2] [path3] ...")
        return 1

    print(f"Adding files to {MNT_DIR / image_type}")
    for raw in args:
        _copy_path_to_image(Path(raw), image_type)

    print()
    _subcmd_ls(image_type, [])
    print("Done! Files copied")
    return 0


def _subcmd_ls(image_type: str, args: list[str]) -> int:
    if args:
        print(f"Usage: zde image {image_type} ls")
        return 1

    mount_dir = MNT_DIR / image_type
    mount_dir.mkdir(parents=True, exist_ok=True)
    for entry in sorted(mount_dir.iterdir(), key=lambda p: p.name):
        stat = entry.stat()
        is_dir = "d" if entry.is_dir() else "-"
        readable = "r"
        writable = "w" if os.access(entry, os.W_OK) else "-"
        executable = "x" if (entry.suffix == ".bin" or "." not in entry.name) else "-"

        size = stat.st_size
        suffix = "B"
        if size > 64 * 1024:
            size = size // 1024
            suffix = "K"

        print(f"{is_dir}{readable}{writable}{executable} {entry.name[:16]:<16}  {size:>8}{suffix}")
    return 0


def _subcmd_rm(image_type: str, args: list[str]) -> int:
    if not args:
        print("Error: No paths provided")
        print(f"Usage: zde image {image_type} rm <path1> [path2] [path3] ...")
        return 1

    mount_dir = MNT_DIR / image_type
    mount_dir.mkdir(parents=True, exist_ok=True)
    for raw in args:
        target = mount_dir / raw
        if not target.exists():
            print(f"Warning: '{raw}' does not exist in {image_type}, skipping")
            continue
        if target.is_dir():
            print(f"  Removing directory: {raw}")
            shutil.rmtree(target)
        else:
            print(f"  Removing file: {raw}")
            target.unlink()

    print()
    _subcmd_ls(image_type, [])
    print("Done! Files removed")
    return 0


def _subcmd_create(image_type: str, args: list[str], default_size: str) -> int:
    if len(args) > 1:
        print(f"Usage: zde image {image_type} create [size]")
        return 1

    if not require_deps(["Zeal8bit/ZealFS"]):
        return 1

    size = args[0] if args else default_size
    image_path = MNT_DIR / f"{image_type}.img"

    if image_path.exists():
        reply = input("Image exists, overwrite? ([Y]es, [N]o) ").strip().lower()
        if reply not in {"y", "yes"}:
            return 1
        image_path.unlink()

    print("Image Name:", image_type)
    print("Image Size:", size)

    (MNT_DIR / "eeprom").mkdir(parents=True, exist_ok=True)
    (MNT_DIR / "cf").mkdir(parents=True, exist_ok=True)
    (MNT_DIR / "sd").mkdir(parents=True, exist_ok=True)
    (MNT_DIR / "tf").mkdir(parents=True, exist_ok=True)

    if image_type == "cf":
        return _pack_cf_image()

    return _build_zealfs_image(image_type, size)


def _help_image_type(image_type: str) -> int:
    print(f"Usage: zde image {image_type} <subcommand> [args]")
    print("Subcommands:")
    print("  add <path1> [path2] [path3] ...")
    print("  rm <path1> [path2] [path3] ...")
    print("  ls")
    print("  create [size]")
    return 0


def _dispatch_image_type(image_type: str, args: list[str], default_size: str) -> int:
    if not args:
        return _help_image_type(image_type)

    subcmd = args[0]
    subargs = args[1:]
    if subcmd in {"help", "-h", "--help"}:
        return _help_image_type(image_type)
    if subcmd == "add":
        return _subcmd_add(image_type, subargs)
    if subcmd == "rm":
        return _subcmd_rm(image_type, subargs)
    if subcmd == "ls":
        return _subcmd_ls(image_type, subargs)
    if subcmd == "create":
        return _subcmd_create(image_type, subargs, default_size)

    print(f"Unknown subcommand: {subcmd}")
    _help_image_type(image_type)
    return 1


def subcmd_eeprom(args: list[str]) -> int:
    return _dispatch_image_type("eeprom", args, "32")


def subcmd_cf(args: list[str]) -> int:
    return _dispatch_image_type("cf", args, "64")


def subcmd_tf(args: list[str]) -> int:
    return _dispatch_image_type("tf", args, "4096")


def help() -> int:
    print("Usage: zde image <subcommand> [args]")
    print("Subcommands:")
    print("  eeprom <add|rm|ls|create> [args]")
    print("  cf <add|rm|ls|create> [args]")
    print("  tf <add|rm|ls|create> [args]")
    return 0


def main(args: list[str]) -> int:
    return help()


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="image",
        label="image",
        help="Manage and build EEPROM/CF/TF images",
        actions=[
            ActionSpec(id="eeprom", label="eeprom", help="Manage EEPROM image staging/build"),
            ActionSpec(id="cf", label="cf", help="Manage CF image staging/build"),
            ActionSpec(id="tf", label="tf", help="Manage TF image staging/build"),
        ],
    )
