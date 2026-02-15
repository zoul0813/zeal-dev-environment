from __future__ import annotations

from mods.update import resolve_env, update_deps


def main(args: list[str]) -> int:
    print("Running in-container update tasks")

    rc = update_deps(resolve_env())
    if rc != 0:
        return rc

    print("In-container update tasks complete")
    return 0
