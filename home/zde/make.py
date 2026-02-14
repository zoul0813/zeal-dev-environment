from __future__ import annotations

import argparse
import os

from common import HOME_DIR
from process import run


def cmd_make(args: argparse.Namespace) -> int:
    if os.environ.get("ASEPRITE_PATH"):
        run(["make", "-f", str(HOME_DIR / "zeal-game-dev-kit" / "aseprite.mk")])
    return run(["make", *args.make_args])
