from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

from mods.common import HOME_DIR, MNT_DIR
from mods.process import run
from mods.requirements import require_deps
from mods.tui.contract import ActionSpec, CommandSpec


IMAGE_TYPES = ("eeprom", "cf", "tf", "romdisk")
IMAGE_SUPPORTS_DIRECTORIES: dict[str, bool] = {
    "eeprom": True,
    "cf": False,
    "tf": True,
    "romdisk": False,
}


def _validate_image_type(image_type: str) -> None:
    if image_type not in IMAGE_TYPES:
        raise ValueError(f"Unknown image type: {image_type}")


def available_stage_targets() -> list[str]:
    return list(IMAGE_TYPES)


def target_supports_directories(image_type: str) -> bool:
    _validate_image_type(image_type)
    return bool(IMAGE_SUPPORTS_DIRECTORIES.get(image_type, False))


def image_root(image_type: str) -> Path:
    _validate_image_type(image_type)
    return MNT_DIR / image_type


def _normalize_stage_root(stage_root: str | None) -> Path:
    if not isinstance(stage_root, str) or not stage_root.strip():
        return Path(".")
    raw = stage_root.strip()
    as_path = Path(raw)
    parts = [part for part in as_path.parts if part not in {"/", "\\"}]
    if not parts:
        return Path(".")
    return Path(*parts)


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


def _rows_for_dir(base_dir: Path) -> list[tuple[str, str]]:
    base_dir.mkdir(parents=True, exist_ok=True)
    rows: list[tuple[str, str]] = []
    for entry in sorted(base_dir.iterdir(), key=lambda p: p.name):
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

        line = f"{is_dir}{readable}{writable}{executable} {entry.name[:16]:<16}  {size:>8}{suffix}"
        rows.append((entry.name, line))
    return rows


def copy_path_to_target(path: Path, image_type: str) -> None:
    _validate_image_type(image_type)
    _copy_path_to_image(path, image_type)


def stage_artifacts_to_target(
    artifacts: list[tuple[Path, Path]],
    image_type: str,
    stage_root: str | None = None,
) -> None:
    _validate_image_type(image_type)
    target_dir = image_root(image_type)
    target_dir.mkdir(parents=True, exist_ok=True)
    supports_dirs = target_supports_directories(image_type)
    root_rel = _normalize_stage_root(stage_root)
    root_base = target_dir / root_rel
    root_base.mkdir(parents=True, exist_ok=True)

    for source_path, rel_hint in artifacts:
        if not source_path.exists():
            print(f"Warning: '{source_path}' does not exist, skipping")
            continue

        if source_path.is_file():
            if supports_dirs:
                dest_path = root_base / rel_hint
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                print(f"  Copying file: {source_path} -> {dest_path}")
                shutil.copy2(source_path, dest_path)
            else:
                dest_path = target_dir / source_path.name
                print(f"  Copying file: {source_path} -> {dest_path}")
                shutil.copy2(source_path, dest_path)
            continue

        if source_path.is_dir():
            if supports_dirs:
                dest_dir = root_base / rel_hint
                dest_dir.parent.mkdir(parents=True, exist_ok=True)
                print(f"  Copying directory tree: {source_path} -> {dest_dir}")
                shutil.copytree(source_path, dest_dir, dirs_exist_ok=True)
            else:
                print(f"  Copying directory contents (top-level files only): {source_path}")
                for child in source_path.iterdir():
                    if child.is_file():
                        shutil.copy2(child, target_dir / child.name)
            continue

        print(f"Warning: '{source_path}' is not a file or directory, skipping")


def image_entries(image_type: str, relative_dir: Path | str = Path(".")) -> list[tuple[str, str, bool]]:
    _validate_image_type(image_type)
    rel = Path(relative_dir)
    target_dir = image_root(image_type) / rel
    rows = _rows_for_dir(target_dir)
    entries: list[tuple[str, str, bool]] = []
    for name, line in rows:
        entries.append((name, line, line.startswith("d")))
    return entries


def image_rows(image_type: str, relative_dir: Path | str = Path(".")) -> list[tuple[str, str]]:
    entries = image_entries(image_type, relative_dir)
    return [(name, line) for name, line, _ in entries]


def subcmd_romdisk(args: list[str]) -> int:
    return _dispatch_image_type("romdisk", args, "", allow_create=False)


def run_image_subcommand(image_type: str, args: list[str]) -> int:
    _validate_image_type(image_type)
    if image_type == "eeprom":
        return subcmd_eeprom(args)
    if image_type == "cf":
        return subcmd_cf(args)
    if image_type == "tf":
        return subcmd_tf(args)
    return subcmd_romdisk(args)


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
    for _, line in _rows_for_dir(mount_dir):
        print(line)
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


def _help_image_type(image_type: str, allow_create: bool = True) -> int:
    print(f"Usage: zde image {image_type} <subcommand> [args]")
    print("Subcommands:")
    print("  add <path1> [path2] [path3] ...")
    print("  rm <path1> [path2] [path3] ...")
    print("  ls")
    if allow_create:
        print("  create [size]")
    return 0


def _dispatch_image_type(image_type: str, args: list[str], default_size: str, allow_create: bool = True) -> int:
    if not args:
        return _help_image_type(image_type, allow_create=allow_create)

    subcmd = args[0]
    subargs = args[1:]
    if subcmd in {"help", "-h", "--help"}:
        return _help_image_type(image_type, allow_create=allow_create)
    if subcmd == "add":
        return _subcmd_add(image_type, subargs)
    if subcmd == "rm":
        return _subcmd_rm(image_type, subargs)
    if subcmd == "ls":
        return _subcmd_ls(image_type, subargs)
    if subcmd == "create" and allow_create:
        return _subcmd_create(image_type, subargs, default_size)

    print(f"Unknown subcommand: {subcmd}")
    return _help_image_type(image_type, allow_create=allow_create)


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
    print("  romdisk <add|rm|ls> [args]")
    return 0


def main(args: list[str]) -> int:
    return help()


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="image",
        label="image",
        help="Manage and build EEPROM/CF/TF images",
        actions=[
            ActionSpec(id="open", label="open", help="Open image media browser"),
        ],
    )


def get_tui_screen():
    from scrns.image_menu import ImageMenuScreen

    return ImageMenuScreen()
