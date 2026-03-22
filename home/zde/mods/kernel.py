from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from mods.common import MNT_DIR, USER_STATE_DIR, ZOS_PATH
from mods.process import run


@dataclass(frozen=True)
class KernelOption:
    action_id: str
    label: str
    help: str
    args: list[str]


@dataclass(frozen=True)
class DepKernelConfig:
    dep_id: str
    aliases: list[str]
    os_conf: Path


def _dep_kernel_config_from_lock(dep_id: str, lock_entry: Any, default_aliases: list[str] | None = None) -> DepKernelConfig | None:
    if not isinstance(lock_entry, dict):
        return None
    dep_root_raw = lock_entry.get("path")
    if not isinstance(dep_root_raw, str) or not dep_root_raw.strip():
        return None
    dep_root = Path(dep_root_raw.strip())
    kernel_cfg = lock_entry.get("kernel_config")
    if not isinstance(kernel_cfg, dict):
        return None
    raw_path = kernel_cfg.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        return None
    cfg_path = Path(raw_path.strip())
    os_conf = cfg_path if cfg_path.is_absolute() else dep_root / cfg_path
    if not os_conf.is_file():
        return None

    raw_aliases = kernel_cfg.get("aliases")
    aliases: list[str] = []
    if isinstance(raw_aliases, list):
        aliases = [alias for alias in raw_aliases if isinstance(alias, str) and alias.strip()]
    if not aliases and default_aliases:
        aliases = [alias for alias in default_aliases if isinstance(alias, str) and alias.strip()]

    return DepKernelConfig(dep_id=dep_id, aliases=aliases, os_conf=os_conf)


def list_kernel_configs() -> list[str]:
    return sorted(_kernel_config_map().keys())


def _kernel_config_map() -> dict[str, str]:
    configs_dir = ZOS_PATH / "configs"
    if not configs_dir.is_dir():
        return {}

    selected: dict[str, str] = {}
    for path in sorted(configs_dir.rglob("*")):
        if not path.is_file() or path.suffix != ".conf":
            continue
        rel = path.relative_to(configs_dir)
        key = rel.with_suffix("").as_posix()
        rel_path = rel.as_posix()
        selected[key] = rel_path
    return selected


def _resolve_builtin_kernel_config_path(raw: str) -> str | None:
    config_name = raw.strip()
    if not config_name:
        return None

    if config_name.startswith("configs/"):
        config_name = config_name[len("configs/") :]

    direct = _kernel_config_map().get(config_name)
    if direct is not None:
        return f"configs/{direct}"

    if config_name.endswith(".conf"):
        config_name = config_name[: -len(".conf")]

    resolved = _kernel_config_map().get(config_name)
    if resolved is None:
        return None
    return f"configs/{resolved}"


def list_dep_kernel_configs() -> list[DepKernelConfig]:
    try:
        from mods.deps import DepCatalog
    except Exception:
        return []

    catalog = DepCatalog()
    rows: list[DepKernelConfig] = []
    for dep in catalog.installed():
        lock_entry = catalog.lock_deps.get(dep.id)
        dep_cfg = _dep_kernel_config_from_lock(dep.id, lock_entry, dep.aliases)
        if dep_cfg is None:
            continue
        rows.append(dep_cfg)
    return sorted(rows, key=lambda row: row.dep_id.casefold())


def _resolve_dep_kernel_config(raw: str) -> DepKernelConfig | None:
    try:
        from mods.deps import DepCatalog
    except Exception:
        return None

    catalog = DepCatalog()
    raw_id = raw.strip()
    if not raw_id:
        return None
    try:
        dep = catalog.resolve(raw_id)
    except RuntimeError:
        return None
    if dep is None or not dep.installed:
        return None
    return _dep_kernel_config_from_lock(dep.id, catalog.lock_deps.get(dep.id), dep.aliases)


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
    for dep_cfg in list_dep_kernel_configs():
        label = dep_cfg.aliases[0] if dep_cfg.aliases else dep_cfg.dep_id
        aliases = ", ".join(dep_cfg.aliases) if dep_cfg.aliases else "-"
        options.append(
            KernelOption(
                action_id=f"dep:{dep_cfg.dep_id}",
                label=label,
                help=f"Build kernel using dep config: {dep_cfg.dep_id} (aliases: {aliases})",
                args=[dep_cfg.dep_id],
            )
        )
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
    zos_path = ZOS_PATH
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
        selected = _resolve_builtin_kernel_config_path(kernel_config) or f"configs/{kernel_config}.conf"
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
    os_conf = ZOS_PATH / "os.conf"
    user_conf_create = False
    builtin_configs = set(list_kernel_configs())
    builtin_special = {"user", "menuconfig", "default"}
    dep_cfg: DepKernelConfig | None = None

    if kernel_config not in builtin_special and kernel_config not in builtin_configs:
        dep_cfg = _resolve_dep_kernel_config(kernel_config)
        if dep_cfg is None:
            print(f"Unknown kernel config: {kernel_config}")
            return 1

    if kernel_config in {"user", "menuconfig"}:
        if user_conf.is_file():
            shutil.copy2(user_conf, os_conf)
            print(f"Copied {user_conf} to {os_conf}")
        else:
            user_conf_create = True
            print(f"Warning: {user_conf} does not exist")
    elif dep_cfg is not None:
        shutil.copy2(dep_cfg.os_conf, os_conf)
        print(f"Copied {dep_cfg.os_conf} to {os_conf}")
        kernel_config = "user"

    rc = build_kernel(kernel_config)

    if rc == 0 and (kernel_config == "menuconfig" or user_conf_create):
        if os_conf.is_file():
            USER_STATE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(os_conf, user_conf)
            print(f"Copied {os_conf} to {user_conf}")

    return rc
