from __future__ import annotations

from pathlib import Path

from mods.process import run
from mods.tui.contract import ActionSpec, CommandSpec


def main(args: list[str]) -> int:
    extra = list(args)
    build_dir = "build"
    if extra and not extra[0].startswith("-"):
        build_dir = extra.pop(0)

    if not Path(build_dir).is_dir():
        print("Generating build directory")
        rc = run(["cmake", "-B", build_dir])
        if rc != 0:
            return rc
    else:
        print("Build directory exists")

    return run(["cmake", "--build", build_dir, *extra])


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="cmake",
        label="cmake",
        help="Configure and build CMake projects",
        actions=[
            ActionSpec(
                id="__main__",
                label="run",
                help="Run cmake with optional build dir and args",
            )
        ],
    )
