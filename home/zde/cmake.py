from __future__ import annotations

from pathlib import Path

from common import dispatch_subcommand
from process import run


def run_cmake(args: list[str]) -> int:
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


SUBCOMMANDS = {
    "run": run_cmake,
}


def main(args: list[str]) -> int:
    return dispatch_subcommand("cmake", args, SUBCOMMANDS, default="run")
