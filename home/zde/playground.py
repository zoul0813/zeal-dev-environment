from __future__ import annotations

from functools import partial

from common import dispatch_subcommand
from emulator import module_help, start_service, stop_service

SUBCOMMANDS = {
    "start": partial(start_service, "playground"),
    "stop": partial(stop_service, "playground"),
}


def help() -> int:
    return module_help("playground")


def main(args: list[str]) -> int:
    return dispatch_subcommand("playground", args, SUBCOMMANDS, default="start", help_fn=help)
