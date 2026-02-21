from __future__ import annotations

import os
import subprocess

from mods.common import HOME_DIR
from mods.tui.contract import ActionSpec, CommandSpec


def main(args: list[str]) -> int:
    env = dict(os.environ)
    env["ZDE_CREATE_OUT"] = "/src"
    try:
        return subprocess.run([str(HOME_DIR / "templates" / "create.sh"), *args], check=False, env=env).returncode
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}")
        return 127


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="create",
        label="create",
        help="Create a new project from templates",
        actions=[
            ActionSpec(
                id="__main__",
                label="run",
                help="Run template project creation",
            )
        ],
    )
