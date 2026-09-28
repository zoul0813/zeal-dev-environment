from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Callable

from mods.common import HOME_DIR, MNT_DIR, ZOS_PATH
from mods.confirmation import confirm
from mods.process import run
from mods.requirements import require_deps
from mods.rom import publish_rom_image
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

    def _confined_path(
        self,
        relative: Path | str,
        *,
        allow_root: bool = False,
        follow_leaf: bool = True,
    ) -> Path:
        relative_path = Path(relative)
        if relative_path.is_absolute() or ".." in relative_path.parts:
            raise ValueError(f"Path escapes {self.image_type} image root: {relative}")
        if not allow_root and relative_path in {Path("."), Path("")}:
            raise ValueError(f"Refusing to operate on {self.image_type} image root")
        if self.root.is_symlink():
            raise ValueError(f"Refusing symlinked {self.image_type} image root")

        root = self.root.resolve()
        candidate = self.root / relative_path
        resolved = candidate.resolve(strict=False)
        if not follow_leaf:
            resolved = candidate.parent.resolve(strict=False) / candidate.name
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"Path escapes {self.image_type} image root: {relative}") from exc
        return candidate

    def _stage_destination(self, relative: Path | str, *, allow_root: bool = False) -> Path:
        destination = self._confined_path(relative, allow_root=allow_root, follow_leaf=False)
        if destination.is_symlink():
            raise ValueError(f"Refusing to stage through symlink: {relative}")
        return destination

    def _build_and_publish(self, build: Callable[[Path], int]) -> int:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        prefix = f".{self.path.name}."
        with tempfile.TemporaryDirectory(prefix=prefix, dir=self.path.parent) as temporary_dir:
            temporary_path = Path(temporary_dir) / self.path.name
            rc = build(temporary_path)
            if rc != 0:
                return rc
            if not temporary_path.is_file():
                print(f"Image build did not produce output: {temporary_path}")
                return 1
            try:
                os.replace(temporary_path, self.path)
            except OSError as exc:
                print(f"Failed to publish image '{self.path}': {exc}")
                return 1
        return 0

    def _normalize_stage_root(self, stage_root: str | None) -> Path:
        if not isinstance(stage_root, str) or not stage_root.strip():
            return Path(".")
        raw = stage_root.strip()
        as_path = Path(raw)
        parts = [part for part in as_path.parts if part not in {"/", "\\"}]
        if not parts:
            return Path(".")
        normalized = Path(*parts)
        if ".." in normalized.parts:
            raise ValueError(f"Stage root escapes {self.image_type} image root: {stage_root}")
        return normalized

    def _copy_path(self, path: Path) -> int:
        if not path.exists():
            print(f"Warning: '{path}' does not exist, skipping")
            return 0

        self.root.mkdir(parents=True, exist_ok=True)
        if path.is_file():
            print(f"  Copying file: {path}")
            try:
                destination = self._stage_destination(path.name)
            except ValueError as exc:
                print(f"Error: {exc}")
                return 1
            shutil.copy2(path, destination)
            return 0

        if path.is_dir():
            print(f"  Copying directory contents (top-level files only): {path}")
            for child in path.iterdir():
                if child.is_file():
                    try:
                        destination = self._stage_destination(child.name)
                    except ValueError as exc:
                        print(f"Error: {exc}")
                        return 1
                    shutil.copy2(child, destination)
            return 0

        print(f"Warning: '{path}' is not a file or directory, skipping")
        return 0

    def entries(self, relative_dir: Path | str = Path(".")) -> list[tuple[str, str, bool]]:
        target_dir = self._confined_path(relative_dir, allow_root=True)
        target_dir.mkdir(parents=True, exist_ok=True)
        rows: list[tuple[str, str, bool]] = []
        for entry in sorted(target_dir.iterdir(), key=lambda p: p.name):
            stat = entry.lstat()
            is_dir = entry.is_dir() and not entry.is_symlink()
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
    ) -> int:
        target_dir = self.root
        target_dir.mkdir(parents=True, exist_ok=True)
        try:
            root_rel = self._normalize_stage_root(stage_root)
            root_base = self._stage_destination(root_rel, allow_root=True)
        except ValueError as exc:
            print(f"Error: {exc}")
            return 1
        root_base.mkdir(parents=True, exist_ok=True)

        for source_path, rel_hint in artifacts:
            if not source_path.exists():
                print(f"Warning: '{source_path}' does not exist, skipping")
                continue

            if source_path.is_file():
                dest_name = rel_hint.name if rel_hint.name else source_path.name
                if self.supports_directories:
                    try:
                        dest_path = self._stage_destination(root_rel / rel_hint)
                    except ValueError as exc:
                        print(f"Error: {exc}")
                        return 1
                    dest_path.parent.mkdir(parents=True, exist_ok=True)
                    print(f"  Copying file: {source_path} -> {dest_path}")
                    shutil.copy2(source_path, dest_path)
                else:
                    try:
                        dest_path = self._stage_destination(dest_name)
                    except ValueError as exc:
                        print(f"Error: {exc}")
                        return 1
                    print(f"  Copying file: {source_path} -> {dest_path}")
                    shutil.copy2(source_path, dest_path)
                continue

            if source_path.is_dir():
                if self.supports_directories:
                    try:
                        dest_dir = self._stage_destination(root_rel / rel_hint, allow_root=True)
                    except ValueError as exc:
                        print(f"Error: {exc}")
                        return 1
                    dest_dir.parent.mkdir(parents=True, exist_ok=True)
                    print(f"  Copying directory tree: {source_path} -> {dest_dir}")
                    shutil.copytree(source_path, dest_dir, dirs_exist_ok=True)
                else:
                    print(f"  Copying directory contents (top-level files only): {source_path}")
                    for child in source_path.iterdir():
                        if child.is_file():
                            try:
                                dest_path = self._stage_destination(child.name)
                            except ValueError as exc:
                                print(f"Error: {exc}")
                                return 1
                            shutil.copy2(child, dest_path)
                continue

            print(f"Warning: '{source_path}' is not a file or directory, skipping")
        return 0

    def add(self, args: list[str]) -> int:
        if not args:
            print("Error: No paths provided")
            print(f"Usage: zde image {self.image_type} add <path1> [path2] [path3] ...")
            return 1

        print(f"Adding files to {self.root}")
        for raw in args:
            rc = self._copy_path(Path(raw))
            if rc not in {None, 0}:
                return int(rc)

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
            try:
                target = self._confined_path(raw, follow_leaf=False)
            except ValueError as exc:
                print(f"Error: {exc}")
                return 1
            if not target.exists() and not target.is_symlink():
                print(f"Warning: '{raw}' does not exist in {self.image_type}, skipping")
                continue
            if target.is_symlink():
                print(f"  Removing symlink: {raw}")
                target.unlink()
            elif target.is_dir():
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
        create_usage: str | None = "create",
        default_create_size: str | None = None,
    ) -> None:
        super().__init__(
            image_type,
            supports_directories=supports_directories,
            create_usage=create_usage,
            default_create_size=default_create_size,
        )

    def create(self, args: list[str]) -> int:
        if args:
            print(f"Usage: zde image {self.image_type} create")
            return 1
        if not self._require_configured_tools():
            return 1

        if not require_deps(["Zeal8bit/ZealFS"]):
            return 1

        if self.path.exists():
            if not confirm("Image exists, overwrite? ([Y]es, [N]o) "):
                return 1

        print(f"Image Name: {self.image_type}")

        self.root.mkdir(parents=True, exist_ok=True)
        return self._build_and_publish(lambda output: self._pack(output, [self.root]))

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

    def _build_image(self, size: str, output: Path | None = None) -> int:
        self.root.mkdir(parents=True, exist_ok=True)
        zealfs_bin = self._TOOLS["zealfs"].path
        media_dir = "/media/zealfs"
        output_path = output or self.path
        cmd = [
            "sudo",
            str(zealfs_bin),
            "-v2",
            f"--image={output_path}",
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
            if not confirm("Image exists, overwrite? ([Y]es, [N]o) "):
                return 1

        print("Image Name:", self.image_type)
        print("Image Size:", size)

        return self._build_and_publish(lambda output: self._build_image(size, output))


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
        os_conf = build_dir / "os.conf"
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

        with tempfile.TemporaryDirectory(prefix=".romdisk.", dir=MNT_DIR) as temporary_dir:
            temporary_root = Path(temporary_dir)
            temporary_disk = temporary_root / disk_img.name
            temporary_output = temporary_root / output_img.name

            rc = self._pack(temporary_disk, pack_inputs, skip_hidden=ignore_hidden)
            if rc != 0:
                return rc
            if not temporary_disk.is_file():
                print(f"ROMDISK build did not produce output: {temporary_disk}")
                return 1

            rc = self._concat(temporary_output, [(0x0000, kernel_bin), (offset_bytes, temporary_disk)])
            if rc != 0:
                return rc
            if not temporary_output.is_file():
                print(f"Combined ROM build did not produce output: {temporary_output}")
                return 1

            try:
                os.replace(temporary_disk, disk_img)
                output_img, latest = publish_rom_image(temporary_output, roms_dir, output_img.name)
            except OSError as exc:
                print(f"Failed to publish ROMDISK images: {exc}")
                return 1

        print(f"Created {disk_img}")
        print(f"Created {output_img}")
        print(f"Linked {latest} -> {output_img.name}")
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
