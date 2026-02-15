from __future__ import annotations

from mods.migrate import migrate_if_legacy
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
