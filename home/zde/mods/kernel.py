from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from mods.common import HOME_DIR, MNT_DIR, USER_STATE_DIR
from mods.process import run


@dataclass(frozen=True)
class KernelOption:
    action_id: str
    label: str
    help: str
    args: list[str]


def list_kernel_configs() -> list[str]:
    configs_dir = HOME_DIR / "Zeal-8-bit-OS" / "configs"
    if not configs_dir.is_dir():
        return []
    return sorted(path.stem for path in configs_dir.glob("*.default"))


def list_kernel_options() -> list[KernelOption]:
    options: list[KernelOption] = [
        KernelOption(
            action_id=f"config:{name}",
            label=name,
            help=f"Build kernel using {name} config",
            args=[name],
        )
        for name in list_kernel_configs()
    ]
    options.append(
        KernelOption(
            action_id="user",
            label="user",
            help="Build using saved user os.conf",
            args=[],
        )
    )
    return options


def _kernel_version(zos_path: Path) -> str:
    errors: list[str] = []
    commitish = re.compile(r"^[0-9a-f]{7,40}$")

    try:
        result = subprocess.run(
            ["git", "-C", str(zos_path), "describe", "--tags", "--always"],
            check=True,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        if value and not commitish.fullmatch(value):
            return value
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        errors.append(f"describe --tags --always failed: {stderr or f'exit {exc.returncode}'}")
    except FileNotFoundError:
        errors.append("git not found in runtime environment")

    # If describe only returned a commit-ish value, prefer the newest fetched tag.
    try:
        result = subprocess.run(
            ["git", "-C", str(zos_path), "for-each-ref", "--sort=-creatordate", "--format=%(refname:short)", "refs/tags"],
            check=True,
            capture_output=True,
            text=True,
        )
        tags = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if tags:
            latest_tag = tags[0]
            try:
                sha_result = subprocess.run(
                    ["git", "-C", str(zos_path), "rev-parse", "--short", "HEAD"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                short_sha = sha_result.stdout.strip()
            except (subprocess.CalledProcessError, FileNotFoundError):
                short_sha = ""
            if short_sha:
                return f"{latest_tag}-{short_sha}"
            return latest_tag
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        errors.append(f"for-each-ref tags failed: {stderr or f'exit {exc.returncode}'}")
    except FileNotFoundError:
        errors.append("git not found while listing refs/tags")

    # Shallow clones may not have enough ancestry for `git describe --tags`.
    # Prefer an exact tag on HEAD when available.
    try:
        result = subprocess.run(
            ["git", "-C", str(zos_path), "tag", "--points-at", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        tags = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if tags:
            return sorted(tags)[-1]
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        errors.append(f"tag --points-at HEAD failed: {stderr or f'exit {exc.returncode}'}")
    except FileNotFoundError:
        errors.append("git not found while listing tags")

    # Fall back to short commit hash so builds remain versioned.
    try:
        result = subprocess.run(
            ["git", "-C", str(zos_path), "rev-parse", "--short", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        value = result.stdout.strip()
        if value:
            return value
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        errors.append(f"rev-parse --short HEAD failed: {stderr or f'exit {exc.returncode}'}")
    except FileNotFoundError:
        errors.append("git not found while reading commit SHA")

    print(f"Warning: kernel version detection failed for {zos_path}")
    for err in errors:
        print(f"  - {err}")
    return "unversioned"


def build_kernel(kernel_config: str) -> int:
    zos_path = HOME_DIR / "Zeal-8-bit-OS"
    fullbin = zos_path / "build" / "os_with_romdisk.img"
    kernel_version = _kernel_version(zos_path)
    cmd_env = os.environ.copy()
    cmd_env["ZEAL_KERNEL_VERSION"] = kernel_version
    build_arg: list[str] = []
    config_arg: list[str] = []
    show_stat = True

    if kernel_config == "user":
        pass
    elif kernel_config == "default":
        print("Creating default config")
        os_conf = zos_path / "os.conf"
        if os_conf.exists():
            os_conf.unlink()
        build_arg = ["--target", "alldefconfig"]
        show_stat = False
    elif kernel_config == "menuconfig":
        print("Launching menuconfig")
        build_arg = ["--target", "menuconfig"]
        show_stat = False
    else:
        selected = f"configs/{kernel_config}.default"
        config_arg = [f"-Dconfig={selected}"]
        print(f"Building {selected} for {kernel_version}")

    print("Zeal 8-bit Kernel Compiler")

    rc = run(["cmake", "-B", "build", *config_arg], cwd=zos_path, env=cmd_env)
    if rc != 0:
        return rc

    rc = run(["cmake", "--build", "build", *build_arg], cwd=zos_path, env=cmd_env)
    if rc != 0:
        return rc

    if not show_stat:
        return 0

    if not fullbin.is_file():
        print(f"Build failed: missing image {fullbin}")
        return 1

    size = fullbin.stat().st_size
    if size <= 0:
        print(f"Build failed: {fullbin} has size 0")
        return 1

    roms_dir = MNT_DIR / "roms"
    roms_dir.mkdir(parents=True, exist_ok=True)
    rom_file = f"zeal8bit-{kernel_version}.img"
    rom_path = roms_dir / rom_file
    shutil.copy2(fullbin, rom_path)
    latest = roms_dir / "latest.img"
    if latest.exists() or latest.is_symlink():
        latest.unlink()
    latest.symlink_to(Path(rom_file))
    print(f"Copied to {rom_path}")
    print(f"Linked {latest} -> {rom_file}")
    return 0


def run_kernel(args: list[str]) -> int:
    kernel_config = args[0] if args else "zeal8bit"
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

    rc = build_kernel(kernel_config)

    if rc == 0 and (kernel_config == "menuconfig" or user_conf_create):
        if os_conf.is_file():
            USER_STATE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(os_conf, user_conf)
            print(f"Copied {os_conf} to {user_conf}")

    return rc


def run_kernel_tui_action(action_id: str, context: dict[str, Any]) -> int:
    action_args = list(context.get("args", []))
    if action_id == "__main__":
        return run_kernel(action_args)
    if action_id == "user":
        return run_kernel(["user", *action_args])
    if action_id == "menuconfig":
        return run_kernel(["menuconfig", *action_args])
    if action_id == "default":
        return run_kernel(["default", *action_args])
    if action_id.startswith("config:"):
        config_name = action_id.split(":", 1)[1]
        if not config_name:
            print("Invalid kernel config action.")
            return 1
        return run_kernel([config_name, *action_args])

    print(f"Unsupported kernel TUI action: {action_id}")
    return 1
