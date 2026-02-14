from __future__ import annotations

from common import HOME_DIR, dispatch_subcommand
from process import run


def run_create(args: list[str]) -> int:
    return run([str(HOME_DIR / "templates" / "create.sh"), *args])


SUBCOMMANDS = {
    "run": run_create,
}


def main(args: list[str]) -> int:
    return dispatch_subcommand("create", args, SUBCOMMANDS, default="run")
