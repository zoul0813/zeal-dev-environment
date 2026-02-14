from __future__ import annotations

from common import dispatch_subcommand
from process import run


def run_shell(args: list[str]) -> int:
    return run(["/bin/bash"])


SUBCOMMANDS = {
    "run": run_shell,
}


def main(args: list[str]) -> int:
    return dispatch_subcommand("shell", args, SUBCOMMANDS, default="run")
