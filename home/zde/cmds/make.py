from __future__ import annotations

import os

from mods.common import HOME_DIR
from mods.process import run
from mods.tui.contract import ActionSpec, CommandSpec


def main(args: list[str]) -> int:
    if os.environ.get("ASEPRITE_PATH"):
        run(["make", "-f", str(HOME_DIR / "zeal-game-dev-kit" / "aseprite.mk")])
    return run(["make", *args])


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="make",
        label="make",
        help="Run make in current project",
        actions=[
            ActionSpec(
                id="__main__",
                label="run",
                help="Run make with optional arguments",
            )
        ],
    )
