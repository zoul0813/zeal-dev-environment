#!/usr/bin/env python3
"""ZDE in-container command router."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
HOME_DIR = Path("/home/zeal8bit") if Path("/home/zeal8bit").is_dir() else SCRIPT_DIR
MNT_DIR = Path("/mnt") if Path("/mnt").is_dir() else SCRIPT_DIR.parent / "mnt"
ROMDISK_DIR = MNT_DIR / "romdisk"
USER_STATE_DIR = HOME_DIR / ".zeal8bit"


def run(cmd: list[str], cwd: Path | None = None) -> int:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False).returncode


def run_checked(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)


def cmd_make(args: argparse.Namespace) -> int:
    if os.environ.get("ASEPRITE_PATH"):
        run(["make", "-f", str(HOME_DIR / "zeal-game-dev-kit" / "aseprite.mk")])
    return run(["make", *args.make_args])


def cmd_cmake(args: argparse.Namespace) -> int:
    extra = list(args.cmake_args)
    build_dir = "build"
    if extra and not extra[0].startswith("-"):
        build_dir = extra.pop(0)

    if not Path(build_dir).is_dir():
        print("Generating build directory")
        rc = run(["cmake", "-B", build_dir])
        if rc != 0:
            return rc
    else:
        print("Build directory exists")

    return run(["cmake", "--build", build_dir, *extra])


def cmd_kernel(args: argparse.Namespace) -> int:
    kernel_config = args.kernel_config or "zeal8bit"
    user_conf = USER_STATE_DIR / "os.conf"
    os_conf = HOME_DIR / "Zeal-8-bit-OS" / "os.conf"
    user_conf_create = False

    if kernel_config in {"user", "menuconfig"}:
        if user_conf.is_file():
            shutil.copy2(user_conf, os_conf)
            print(f"Copied {user_conf} to {os_conf}")
        else:
            user_conf_create = True
            print(f"Warning: {user_conf} does not exist")

    rc = run([str(HOME_DIR / "kernel.sh"), kernel_config])

    if rc == 0 and (kernel_config == "menuconfig" or user_conf_create):
        if os_conf.is_file():
            USER_STATE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(os_conf, user_conf)
            print(f"Copied {os_conf} to {user_conf}")

    return rc


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


def cmd_create(args: argparse.Namespace) -> int:
    return run([str(HOME_DIR / "templates" / "create.sh"), *args.create_args])


def copy_path_to_romdisk(path: Path) -> None:
    if not path.exists():
        print(f"Warning: '{path}' does not exist, skipping")
        return

    ROMDISK_DIR.mkdir(parents=True, exist_ok=True)
    if path.is_file():
        print(f"  Copying file: {path}")
        shutil.copy2(path, ROMDISK_DIR / path.name)
        return

    if path.is_dir():
        print(f"  Copying directory contents (top-level files only): {path}")
        for child in path.iterdir():
            if child.is_file():
                shutil.copy2(child, ROMDISK_DIR / child.name)
        return

    print(f"Warning: '{path}' is not a file or directory, skipping")


def cmd_romdisk_add(args: argparse.Namespace) -> int:
    if not args.paths:
        print("Error: No paths provided")
        print("Usage: zde romdisk add <path1> [path2] [path3] ...")
        return 1

    print(f"Adding files to romdisk at {ROMDISK_DIR}")
    for raw in args.paths:
        copy_path_to_romdisk(Path(raw))

    cmd_romdisk_ls()
    print("Done! Files copied to romdisk")
    return 0


def cmd_romdisk_rm(args: argparse.Namespace) -> int:
    if not args.paths:
        print("Error: No paths provided")
        print("Usage: zde romdisk rm <path1> [path2] [path3] ...")
        return 1

    for raw in args.paths:
        target = ROMDISK_DIR / raw
        if not target.exists():
            print(f"Warning: '{raw}' does not exist in romdisk, skipping")
            continue
        if target.is_dir():
            print(f"  Removing directory: {raw}")
            shutil.rmtree(target)
        else:
            print(f"  Removing file: {raw}")
            target.unlink()

    print()
    cmd_romdisk_ls()
    print("Done! Files removed from romdisk")
    return 0


def cmd_romdisk_ls() -> int:
    ROMDISK_DIR.mkdir(parents=True, exist_ok=True)
    for entry in sorted(ROMDISK_DIR.iterdir(), key=lambda p: p.name):
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


def cmd_emulator(mode: str, query: str | None) -> int:
    status_rc = run(["/opt/penv/bin/supervisorctl", "status", mode])
    if status_rc == 3:
        if mode == "playground":
            run_checked(
                [
                    "/opt/penv/bin/python3",
                    str(HOME_DIR / "Zeal-Playground" / "tools" / "build_manifest.py"),
                    str(HOME_DIR / "Zeal-Playground" / "files"),
                    str(HOME_DIR / "Zeal-Playground" / "files" / "manifest.json"),
                ]
            )
        start_rc = run(["/opt/penv/bin/supervisorctl", "start", mode])
        if start_rc != 0:
            return start_rc
    elif status_rc != 0:
        return status_rc

    base = "http://127.0.0.1:1145/?r=latest&"
    if mode == "playground":
        base = "http://127.0.0.1:1155/?r=latest&"
    print(base + (query or ""))
    return 0


def cmd_emulator_stop(mode: str) -> int:
    status_rc = run(["/opt/penv/bin/supervisorctl", "status", mode])
    if status_rc == 0:
        return run(["/opt/penv/bin/supervisorctl", "stop", mode])
    return 0


def interactive_shell() -> int:
    return run(["/bin/bash"])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zde")
    sub = parser.add_subparsers(dest="command")

    make_p = sub.add_parser("make")
    make_p.add_argument("make_args", nargs=argparse.REMAINDER)

    cmake_p = sub.add_parser("cmake")
    cmake_p.add_argument("cmake_args", nargs=argparse.REMAINDER)

    kernel_p = sub.add_parser("kernel")
    kernel_p.add_argument("kernel_config", nargs="?")

    image_p = sub.add_parser("image")
    image_p.add_argument("image_type", choices=["eeprom", "cf", "tf"])
    image_p.add_argument("size", nargs="?")

    create_p = sub.add_parser("create")
    create_p.add_argument("create_args", nargs=argparse.REMAINDER)

    romdisk_p = sub.add_parser("romdisk")
    rom_sub = romdisk_p.add_subparsers(dest="romdisk_cmd")

    rom_add = rom_sub.add_parser("add")
    rom_add.add_argument("paths", nargs="+")

    rom_rm = rom_sub.add_parser("rm")
    rom_rm.add_argument("paths", nargs="+")

    rom_sub.add_parser("ls")

    emu_p = sub.add_parser("emu")
    emu_p.add_argument("mode", nargs="?", default="start", choices=["start", "stop"])
    emu_p.add_argument("query", nargs="?")

    emulator_p = sub.add_parser("emulator")
    emulator_p.add_argument("mode", nargs="?", default="start", choices=["start", "stop"])
    emulator_p.add_argument("query", nargs="?")

    pg_p = sub.add_parser("playground")
    pg_p.add_argument("mode", nargs="?", default="start", choices=["start", "stop"])
    pg_p.add_argument("query", nargs="?")

    sub.add_parser("activate")

    for name in ["update", "status", "start", "stop", "restart", "rebuild"]:
        sub.add_parser(name)

    return parser


def main(argv: list[str]) -> int:
    if not argv:
        print("Help: update, status, start, stop, make, emu[lator], create, image, kernel, romdisk")
        return 0

    if argv[0] == "-i":
        return interactive_shell()

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "make":
        return cmd_make(args)
    if args.command == "cmake":
        return cmd_cmake(args)
    if args.command == "kernel":
        return cmd_kernel(args)
    if args.command == "image":
        return cmd_image(args)
    if args.command == "create":
        return cmd_create(args)
    if args.command == "romdisk":
        if args.romdisk_cmd == "add":
            return cmd_romdisk_add(args)
        if args.romdisk_cmd == "rm":
            return cmd_romdisk_rm(args)
        return cmd_romdisk_ls()
    if args.command in {"emu", "emulator"}:
        if args.mode == "stop":
            return cmd_emulator_stop("emulator")
        return cmd_emulator("emulator", args.query)
    if args.command == "playground":
        if args.mode == "stop":
            return cmd_emulator_stop("playground")
        return cmd_emulator("playground", args.query)

    if args.command == "activate":
        print("This command is host-only: use eval \"$(zde activate)\" from the host shell.")
        return 1

    if args.command in {"update", "status", "start", "stop", "restart", "rebuild"}:
        print(f"This command is host/container lifecycle management and is not supported in-container: {args.command}")
        return 1

    print("Help: update, status, start, stop, make, emu[lator], create, image, kernel, romdisk")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
