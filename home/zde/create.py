from __future__ import annotations

import argparse

from common import HOME_DIR
from process import run


def cmd_create(args: argparse.Namespace) -> int:
    return run([str(HOME_DIR / "templates" / "create.sh"), *args.create_args])
