from __future__ import annotations

from mods.migrate import migrate_if_legacy
from mods.tui.contract import ActionSpec, CommandSpec
from mods.update import resolve_env, update_deps


def main(args: list[str]) -> int:
    print("Running in-container update tasks")

    env = resolve_env()
    rc = migrate_if_legacy(env)
    if rc != 0:
        return rc

    rc = update_deps(env)
    if rc != 0:
        return rc

    print("In-container update tasks complete")
    return 0


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="update",
        label="update",
        help="Sync required dependencies and lock state",
        actions=[
            ActionSpec(id="__main__", label="run", help="Run dependency update/migration tasks"),
        ],
    )
