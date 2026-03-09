from __future__ import annotations

import os
import shutil
from pathlib import Path

from mods.common import HOME_DIR, MNT_DIR, ZOS_PATH
from mods.process import run
from mods.requirements import require_deps
from mods.tooling import ToolSpec, ToolingSupport


class Image(ToolingSupport):
    def __init__(
        self,
        image_type: str,
        *,
        supports_directories: bool,
        create_usage: str | None = None,
        default_create_size: str | None = None,
    ) -> None:
        super().__init__()
        self.image_type = image_type
        self.supports_directories = supports_directories
        self.create_usage = create_usage
        self.default_create_size = default_create_size

    @property
    def root(self) -> Path:
        return MNT_DIR / self.image_type

    @property
    def path(self) -> Path:
        return MNT_DIR / f"{self.image_type}.img"

    def _normalize_stage_root(self, stage_root: str | None) -> Path:
        if not isinstance(stage_root, str) or not stage_root.strip():
            return Path(".")
        raw = stage_root.strip()
        as_path = Path(raw)
        parts = [part for part in as_path.parts if part not in {"/", "\\"}]
        if not parts:
            return Path(".")
        return Path(*parts)

    def _copy_path(self, path: Path) -> None:
        if not path.exists():
            print(f"Warning: '{path}' does not exist, skipping")
            return

        self.root.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            print(f"  Copying file: {path}")
            shutil.copy2(path, self.root / path.name)
            return

        if path.is_dir():
            print(f"  Copying directory contents (top-level files only): {path}")
            for child in path.iterdir():
                if child.is_file():
                    shutil.copy2(child, self.root / child.name)
            return

        print(f"Warning: '{path}' is not a file or directory, skipping")

    def entries(self, relative_dir: Path | str = Path(".")) -> list[tuple[str, str, bool]]:
        target_dir = self.root / Path(relative_dir)
        target_dir.mkdir(parents=True, exist_ok=True)
        rows: list[tuple[str, str, bool]] = []
        for entry in sorted(target_dir.iterdir(), key=lambda p: p.name):
            stat = entry.stat()
            is_dir = entry.is_dir()
            readable = "r"
            writable = "w" if os.access(entry, os.W_OK) else "-"
            executable = "x" if (entry.suffix == ".bin" or "." not in entry.name) else "-"

            size = stat.st_size
            suffix = "B"
            if size > 64 * 1024:
                size = size // 1024
                suffix = "K"

            line = f"{'d' if is_dir else '-'}{readable}{writable}{executable} {entry.name[:16]:<16}  {size:>8}{suffix}"
            rows.append((entry.name, line, is_dir))
        return rows

    def stage_artifacts(
        self,
        artifacts: list[tuple[Path, Path]],
        stage_root: str | None = None,
    ) -> None:
        target_dir = self.root
        target_dir.mkdir(parents=True, exist_ok=True)
        root_rel = self._normalize_stage_root(stage_root)
        root_base = target_dir / root_rel
        root_base.mkdir(parents=True, exist_ok=True)

        for source_path, rel_hint in artifacts:
            if not source_path.exists():
                print(f"Warning: '{source_path}' does not exist, skipping")
                continue

            if source_path.is_file():
                dest_name = rel_hint.name if rel_hint.name else source_path.name
                if self.supports_directories:
                    dest_path = root_base / rel_hint
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    print(f"  Copying file: {source_path} -> {dest_path}")
                    shutil.copy2(source_path, dest_path)
                else:
                    dest_path = target_dir / dest_name
                    print(f"  Copying file: {source_path} -> {dest_path}")
                    shutil.copy2(source_path, dest_path)
                continue

            if source_path.is_dir():
                if self.supports_directories:
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

    def add(self, args: list[str]) -> int:
        if not args:
            print("Error: No paths provided")
            print(f"Usage: zde image {self.image_type} add <path1> [path2] [path3] ...")
            return 1

        print(f"Adding files to {self.root}")
        for raw in args:
            self._copy_path(Path(raw))

        print()
        self.ls([])
        print("Done! Files copied")
        return 0

    def rm(self, args: list[str]) -> int:
        if not args:
            print("Error: No paths provided")
            print(f"Usage: zde image {self.image_type} rm <path1> [path2] [path3] ...")
            return 1

        self.root.mkdir(parents=True, exist_ok=True)
        for raw in args:
            target = self.root / raw
            if not target.exists():
                print(f"Warning: '{raw}' does not exist in {self.image_type}, skipping")
                continue
            if target.is_dir():
                print(f"  Removing directory: {raw}")
                shutil.rmtree(target)
            else:
                print(f"  Removing file: {raw}")
                target.unlink()

        print()
        self.ls([])
        print("Done! Files removed")
        return 0

    def ls(self, args: list[str]) -> int:
        if args:
            print(f"Usage: zde image {self.image_type} ls")
            return 1

        for _, line, _ in self.entries():
            print(line)
        return 0

    def create(self, args: list[str]) -> int:
        print(f"Create is not supported for {self.image_type}")
        return 1

    def help(self) -> int:
        print(f"Usage: zde image {self.image_type} <subcommand> [args]")
        print("Subcommands:")
        print("  add <path1> [path2] [path3] ...")
        print("  rm <path1> [path2] [path3] ...")
        print("  ls")
        if self.create_usage is not None:
            print(f"  {self.create_usage}")
        return 0


class ImagePack(Image):
    _TOOLS: dict[str, ToolSpec] = {
        "pack": ToolSpec(ZOS_PATH / "tools" / "pack.py", required=True),
        "concat": ToolSpec(ZOS_PATH / "tools" / "concat.py"),
    }

    def __init__(
        self,
        image_type: str,
        *,
        supports_directories: bool = False,
        create_usage: str | None = "create [size]",
        default_create_size: str | None = "64",
    ) -> None:
        super().__init__(
            image_type,
            supports_directories=supports_directories,
            create_usage=create_usage,
            default_create_size=default_create_size,
        )

    def create(self, args: list[str]) -> int:
        if not self._require_configured_tools():
            return 1
        if len(args) > 1:
            print(f"Usage: zde image {self.image_type} create [size]")
            return 1

        if not require_deps(["Zeal8bit/ZealFS"]):
            return 1

        if self.path.exists():
            reply = input("Image exists, overwrite? ([Y]es, [N]o) ").strip().lower()
            if reply not in {"y", "yes"}:
                return 1
            self.path.unlink()

        size = args[0] if args else (self.default_create_size or "")
        print(f"Image Name: {self.image_type}")
        print(f"Image Size: {size}")

        self.root.mkdir(parents=True, exist_ok=True)
        return self._pack(self.path, [self.root])

    def _pack(self, output: Path, inputs: list[Path], *, skip_hidden: bool = False) -> int:
        cmd: list[str] = []
        if skip_hidden:
            cmd.append("--skip-hidden")
        cmd.append(str(output))
        cmd.extend(str(path) for path in inputs)
        return self._tool("pack", cmd)

    def _concat(self, output: Path, parts: list[tuple[int, Path]]) -> int:
        cmd = [str(output)]
        for address, path in parts:
            cmd.extend([hex(address), str(path)])
        return self._tool("concat", cmd)


class ImageZealFS(Image):
    _TOOLS: dict[str, ToolSpec] = {
        "zealfs": ToolSpec(HOME_DIR / "ZealFS" / "build" / "zealfs", required=True),
    }

    def __init__(self, image_type: str, default_size: str) -> None:
        super().__init__(
            image_type,
            supports_directories=True,
            create_usage="create [size]",
            default_create_size=default_size,
        )
        self.default_size = default_size

    def _build_image(self, size: str) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        zealfs_bin = self._TOOLS["zealfs"].path
        media_dir = "/media/zealfs"
        cmd = [
            "sudo",
            str(zealfs_bin),
            "-v2",
            f"--image={self.path}",
            f"--size={size}",
        ]
        if self.image_type == "tf":
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
                f"{self.root}/",
                f"{media_dir}/",
            ]
        )
        if rc != 0:
            return rc
        return run(["sudo", "umount", media_dir])

    def create(self, args: list[str]) -> int:
        if len(args) > 1:
            print(f"Usage: zde image {self.image_type} create [size]")
            return 1

        if not self._require_tools(["zealfs"]):
            return 1

        if not require_deps(["Zeal8bit/ZealFS"]):
            return 1

        size = args[0] if args else self.default_size
        if self.path.exists():
            reply = input("Image exists, overwrite? ([Y]es, [N]o) ").strip().lower()
            if reply not in {"y", "yes"}:
                return 1
            self.path.unlink()

        print("Image Name:", self.image_type)
        print("Image Size:", size)

        return self._build_image(size)


class ImageRomdisk(ImagePack):
    _TOOLS: dict[str, ToolSpec] = {
        "pack": ToolSpec(ZOS_PATH / "tools" / "pack.py", required=True),
        "concat": ToolSpec(ZOS_PATH / "tools" / "concat.py", required=True),
    }

    def __init__(self) -> None:
        super().__init__(
            "romdisk",
            create_usage="create",
        )

    def _read_os_conf_value(self, os_conf: Path, key: str) -> str | None:
        if not os_conf.is_file():
            return None
        prefix = f"{key}="
        for raw in os_conf.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if not line.startswith(prefix):
                continue
            value = line[len(prefix) :].strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
                value = value[1:-1]
            return value
        return None

    def _parse_conf_bool(self, value: str | None) -> bool:
        if value is None:
            return False
        return value.strip().lower() in {"y", "yes", "1", "true", "on"}

    def create(self, args: list[str]) -> int:
        if not self._require_tools(["pack", "concat"]):
            return 1

        if args:
            print("Usage: zde image romdisk create")
            return 1

        zos_path = ZOS_PATH
        build_dir = zos_path / "build"
        os_conf = zos_path / "os.conf"
        stage_dir = MNT_DIR / "romdisk"
        roms_dir = MNT_DIR / "roms"
        kernel_bin = build_dir / "os.bin"
        disk_img = self.path
        output_img = roms_dir / "os_with_romdisk.img"

        if not kernel_bin.is_file():
            print(f"Missing kernel build artifact: {kernel_bin}")
            print("Build the kernel first: zde kernel <config>")
            return 1
        if not stage_dir.is_dir():
            print(f"Missing romdisk stage directory: {stage_dir}")
            print("Stage files first: zde image romdisk add <path...>")
            return 1
        offset_pages_raw = self._read_os_conf_value(os_conf, "CONFIG_ROMDISK_OFFSET_PAGES")
        try:
            offset_pages = int(offset_pages_raw) if offset_pages_raw is not None else 1
        except ValueError:
            print(f"Invalid CONFIG_ROMDISK_OFFSET_PAGES in {os_conf}: {offset_pages_raw}")
            return 1
        if offset_pages <= 0:
            print(f"Invalid CONFIG_ROMDISK_OFFSET_PAGES: {offset_pages} (must be > 0)")
            return 1

        include_init_bin = self._parse_conf_bool(self._read_os_conf_value(os_conf, "CONFIG_ROMDISK_INCLUDE_INIT_BIN"))
        ignore_hidden = self._parse_conf_bool(self._read_os_conf_value(os_conf, "CONFIG_ROMDISK_IGNORE_HIDDEN"))
        init_bin = build_dir / "romdisk" / "init" / "build" / "init.bin"

        roms_dir.mkdir(parents=True, exist_ok=True)

        offset_bytes = offset_pages * 0x4000
        kernel_size = kernel_bin.stat().st_size
        if kernel_size > offset_bytes:
            print("Kernel image is bigger than configured ROMDISK offset:")
            print(f"  kernel={kernel_bin} ({kernel_size} bytes)")
            print(f"  offset={offset_bytes} bytes")
            print("Increase CONFIG_ROMDISK_OFFSET_PAGES or rebuild with a smaller kernel.")
            return 1

        pack_inputs: list[Path] = []
        if include_init_bin and init_bin.is_file():
            pack_inputs.append(init_bin)
        elif include_init_bin:
            print(f"Warning: CONFIG_ROMDISK_INCLUDE_INIT_BIN=y but '{init_bin}' is missing")
        pack_inputs.append(stage_dir)

        rc = self._pack(disk_img, pack_inputs, skip_hidden=ignore_hidden)
        if rc != 0:
            return rc

        rc = self._concat(output_img, [(0x0000, kernel_bin), (offset_bytes, disk_img)])
        if rc != 0:
            return rc

        print(f"Created {disk_img}")
        print(f"Created {output_img}")
        return 0


_IMAGE_HANDLERS: dict[str, Image] = {
    "eeprom": ImageZealFS("eeprom", "32"),
    "cf": ImagePack("cf"),
    "tf": ImageZealFS("tf", "4096"),
    "romdisk": ImageRomdisk(),
}

def get_image(image_type: str) -> Image:
    image = _IMAGE_HANDLERS.get(image_type)
    if image is None:
        raise ValueError(f"Unknown image type: {image_type}")
    return image



def images() -> list[Image]:
    return list(_IMAGE_HANDLERS.values())

def image_entries(image_type: str, relative_dir: Path | str = Path(".")) -> list[tuple[str, str, bool]]:
    return get_image(image_type).entries(relative_dir)
