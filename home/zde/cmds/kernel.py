from __future__ import annotations

import shutil

from mods.common import HOME_DIR, USER_STATE_DIR
from mods.process import run
from mods.tui.contract import ActionSpec, CommandSpec


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

    rc = run([str(HOME_DIR / "kernel.sh"), kernel_config])

    if rc == 0 and (kernel_config == "menuconfig" or user_conf_create):
        if os_conf.is_file():
            USER_STATE_DIR.mkdir(parents=True, exist_ok=True)
            shutil.copy2(os_conf, user_conf)
            print(f"Copied {os_conf} to {user_conf}")

    return rc


def subcmd_user(args: list[str]) -> int:
    return run_kernel(["user", *args])


def subcmd_menuconfig(args: list[str]) -> int:
    return run_kernel(["menuconfig", *args])


def main(args: list[str]) -> int:
    return run_kernel(args)


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="kernel",
        label="kernel",
        help="Build kernel with target/user configs",
        actions=[
            ActionSpec(id="__main__", label="run", help="Build kernel with default or provided config"),
            ActionSpec(id="user", label="user", help="Build using saved user os.conf"),
            ActionSpec(id="menuconfig", label="menuconfig", help="Open kernel menuconfig and persist user config"),
        ],
    )
