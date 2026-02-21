#!/usr/bin/env python3
"""ZDE in-container command router."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from mods.commands import (
    DEFAULT_MODULE_ALIASES,
    command_to_module_name,
    discover_command_modules,
    discover_subcommands,
    import_command_module,
    module_name_to_command,
)
from mods.requirements import require_deps

COMMAND_REDIRECTS: dict[str, tuple[str, list[str]]] = {
    # Legacy top-level romdisk command now lives under image.
    "romdisk": ("image", ["romdisk"]),
}


def print_top_help() -> int:
    module_names = discover_command_modules()

    rendered: list[str] = []
    for module_name in module_names:
        name = module_name_to_command(module_name)
        aliases = DEFAULT_MODULE_ALIASES.get(module_name, [])
        if aliases:
            rendered.append(f"{name} ({', '.join(sorted(aliases))})")
        else:
            rendered.append(name)
    print(f"Help: {', '.join(rendered)}")
    return 0


def infer_module_help(module_name: str, subcommands: dict[str, Callable[[list[str]], int]]) -> int:
    visible = sorted(name for name in subcommands if not name.startswith("_"))
    print(f"Usage: zde {module_name} <subcommand> [args]")
    print("Subcommands:")
    for name in visible:
        print(f"  {name}")
    return 0


def main(argv: list[str]) -> int:
    if not argv or argv[0] == "help":
        return print_top_help()

    command_name = argv[0]
    normalized_command = command_name.replace("-", "_")
    redirected = COMMAND_REDIRECTS.get(normalized_command)
    prepend_args: list[str] = []
    if redirected is not None:
        command_name = redirected[0]
        prepend_args = list(redirected[1])
    module_name = command_to_module_name(command_name, DEFAULT_MODULE_ALIASES)
    module_path = f"cmds.{module_name}"
    module_args = [*prepend_args, *argv[1:]]

    try:
        module = import_command_module(module_name)
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

    required = getattr(module, "REQUIRED_DEPS", [])
    if required and not require_deps(list(required)):
        return 1

    if module_args:
        subcmd = module_args[0]
        subhandler = subcommands.get(subcmd)
        if callable(subhandler):
            return int(subhandler(module_args[1:]))

    return int(entry(module_args))


if __name__ == "__main__":
    rc = int(main(sys.argv[1:]))
    if rc != 0 and os.environ.get("ZDE_SOFT_EXIT", "0") == "1":
        rc = 0
    sys.exit(rc)
