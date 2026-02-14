from __future__ import annotations

import os

from common import HOME_DIR, dispatch_subcommand
from process import run


def run_make(args: list[str]) -> int:
    if os.environ.get("ASEPRITE_PATH"):
        run(["make", "-f", str(HOME_DIR / "zeal-game-dev-kit" / "aseprite.mk")])
    return run(["make", *args])


SUBCOMMANDS = {
    "run": run_make,
}


def main(args: list[str]) -> int:
    return dispatch_subcommand("make", args, SUBCOMMANDS, default="run")
