from __future__ import annotations

import os

from mods.process import run
from mods.tui.contract import ActionSpec, CommandSpec


def help() -> int:
    print("Usage: zde test [pytest-args...]")
    print("Runs Python unit tests for ZDE code.")
    print("Common flags: -v, -vv, -k <expr>, -s, --maxfail=1, --lf")
    print("Examples:")
    print("  zde test")
    print("  zde test -v")
    print("  zde test -vv")
    print("  zde test -k config")
    print("  zde test -s")
    print("  zde test --cov=home/zde/mods --cov-report=term-missing")
    return 0


def main(args: list[str]) -> int:
    if args and args[0] in {"help", "-h", "--help"}:
        return help()
    if not args:
        args = ["home/zde/tests"]
    has_cov = any(arg == "--cov" or arg.startswith("--cov=") for arg in args)
    has_cov_config = any(arg.startswith("--cov-config=") or arg == "--cov-config" for arg in args)
    if has_cov and not has_cov_config:
        args = [*args, "--cov-config=home/zde/tests/.coveragerc"]
    env = dict(os.environ)
    env.setdefault("COVERAGE_FILE", "home/zde/tests/.coverage")
    return run(["pytest", "-c", "home/zde/tests/pytest.ini", *args], env=env)


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="test",
        label="test",
        help="Run ZDE Python unit tests",
        actions=[
            ActionSpec(
                id="__main__",
                label="run",
                help="Run pytest with optional arguments",
            )
        ],
    )
