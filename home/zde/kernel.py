from __future__ import annotations

import argparse
import shutil

from common import HOME_DIR, USER_STATE_DIR
from process import run


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
