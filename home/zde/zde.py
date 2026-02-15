#!/usr/bin/env python3
"""ZDE in-container command router."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Callable
from types import ModuleType

HELP_TEXT = "Help: update, deps, activate, make, cmake, kernel, image, create, romdisk, emu[lator], playground"


MODULE_ALIASES = {
    "emu": "emulator",
}


def print_top_help() -> int:
    print(HELP_TEXT)
    return 0


def infer_module_help(module_name: str, subcommands: dict[str, Callable[[list[str]], int]]) -> int:
    visible = sorted(name for name in subcommands if not name.startswith("_"))
    print(f"Usage: zde {module_name} <subcommand> [args]")
    print("Subcommands:")
    for name in visible:
        print(f"  {name}")
    return 0


def discover_subcommands(module: ModuleType) -> dict[str, Callable[[list[str]], int]]:
    subcommands: dict[str, Callable[[list[str]], int]] = {}
    for name in dir(module):
        if not name.startswith("subcmd_"):
            continue
        handler = getattr(module, name)
        if not callable(handler):
            continue
        subcommands[name.removeprefix("subcmd_")] = handler
    return subcommands


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "help":
        return print_top_help()

    command_name = argv[0]
    module_name = MODULE_ALIASES.get(command_name, command_name).replace("-", "_")
    module_path = f"cmds.{module_name}"
    module_args = argv[1:]

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        if exc.name in {module_path, module_name}:
            print(f"Unknown command module: {module_name}")
            return print_top_help()
        raise

    entry = getattr(module, "main", None)
    if entry is None:
        print(f"Command module '{module_name}' does not define main(args)")
        return 1

    subcommands = discover_subcommands(module)
    if module_args and module_args[0] == "help":
        module_help = getattr(module, "help", None)
        if callable(module_help):
            return int(module_help())
        if subcommands:
            return infer_module_help(command_name, subcommands)

    if module_args:
        subcmd = module_args[0]
        subhandler = subcommands.get(subcmd)
        if callable(subhandler):
            return int(subhandler(module_args[1:]))

    return int(entry(module_args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
