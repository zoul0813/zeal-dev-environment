from __future__ import annotations

from cmds.update import run_maintenance
from mods.tui.contract import ActionSpec, CommandSpec


def main(args: list[str]) -> int:
    if args:
        print("Usage: zde sync")
        return 1
    return run_maintenance()


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="sync",
        label="sync",
        help="Sync ZDE dependencies without updating the ZDE checkout",
        actions=[
            ActionSpec(id="__main__", label="run", help="Run dependency update/migration tasks"),
        ],
    )
