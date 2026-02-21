from __future__ import annotations

import os
import shutil
from pathlib import Path

from mods.common import ROMDISK_DIR
from mods.tui.contract import ActionSpec, CommandSpec


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


def subcmd_add(args: list[str]) -> int:
    if not args:
        print("Error: No paths provided")
        print("Usage: zde romdisk add <path1> [path2] [path3] ...")
        return 1

    print(f"Adding files to romdisk at {ROMDISK_DIR}")
    for raw in args:
        copy_path_to_romdisk(Path(raw))

    subcmd_ls([])
    print("Done! Files copied to romdisk")
    return 0


def subcmd_rm(args: list[str]) -> int:
    if not args:
        print("Error: No paths provided")
        print("Usage: zde romdisk rm <path1> [path2] [path3] ...")
        return 1

    for raw in args:
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
    subcmd_ls([])
    print("Done! Files removed from romdisk")
    return 0


def subcmd_ls(args: list[str]) -> int:
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


def help() -> int:
    print("Usage: zde romdisk <subcommand> [args]")
    print("Subcommands:")
    print("  ls")
    print("  add <path1> [path2] [path3] ...")
    print("  rm <path1> [path2] [path3] ...")
    return 0


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="romdisk",
        label="romdisk",
        help="Romdisk file staging",
        actions=[
            ActionSpec(id="ls", label="ls", help="List romdisk files", pause_after_run=True),
            ActionSpec(id="add", label="add", help="Copy files into romdisk"),
            ActionSpec(id="rm", label="rm", help="Remove files from romdisk"),
        ],
    )


def main(args: list[str]) -> int:
    if not args:
        return subcmd_ls([])
    return subcmd_ls(args)
