from __future__ import annotations

from ._service import start as start_supervised_service
from ._service import stop as stop_supervised_service
from mods.tui.contract import ActionSpec, CommandSpec


def subcmd_start(args: list[str]) -> int:
    query = args[0] if args else None
    start_rc = start_supervised_service("emulator")
    if start_rc != 0:
        return start_rc

    print("http://127.0.0.1:1145/?r=latest&" + (query or ""))
    return 0


def subcmd_stop(args: list[str]) -> int:
    return stop_supervised_service("emulator")


def help() -> int:
    print("Usage: zde emulator <subcommand> [query]")
    print("Subcommands:")
    print("  start [query]")
    print("  stop")
    return 0


def main(args: list[str]) -> int:
    return subcmd_start(args)


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="emulator",
        label="emulator",
        help="Manage Zeal Web Emulator service",
        actions=[
            ActionSpec(id="start", label="start", help="Start emulator service and print URL"),
            ActionSpec(id="stop", label="stop", help="Stop emulator service"),
        ],
    )
