from __future__ import annotations

import os

from common import HOME_DIR
from process import run


def main(args: list[str]) -> int:
    if os.environ.get("ASEPRITE_PATH"):
        run(["make", "-f", str(HOME_DIR / "zeal-game-dev-kit" / "aseprite.mk")])
    return run(["make", *args])
