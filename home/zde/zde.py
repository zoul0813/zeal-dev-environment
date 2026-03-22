#!/usr/bin/env python3
"""ZDE in-container command router."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable

from mods.commands import (
    build_alias_lookup,
    command_to_module_name,
    discover_command_modules,
    discover_subcommands,
    import_command_module,
    module_name_to_command,
)
from mods.requirements import require_deps

SERVICE_COMMANDS: dict[str, dict[str, object]] = {
    "emulator": {
        "aliases": ["emu"],
        "help": "Host-only service command (opens Zeal Web Emulator).",
        "subcommands": ["start", "stop", "status"],
    },
    "playground": {
        "aliases": [],
        "help": "Host-only service command (opens Zeal Playground).",
        "subcommands": ["start", "stop", "status"],
    },
}

COMMAND_REDIRECTS: dict[str, tuple[str, list[str]]] = {
    # Legacy top-level romdisk command now lives under image.
    "romdisk": ("image", ["romdisk"]),
}


def print_top_help() -> int:
    module_names = discover_command_modules()

    rendered: list[str] = []
    for module_name in module_names:
        name = module_name_to_command(module_name)
        rendered.append(name)
    print(f"Commands:\n   {', '.join(rendered)}")

    print("\nHost Commands:\n   exec, activate, update, rebuild")

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
    service_aliases = {
        name: [alias for alias in spec.get("aliases", []) if isinstance(alias, str)]
        for name, spec in SERVICE_COMMANDS.items()
    }
    service_lookup = build_alias_lookup(service_aliases)
    service_name = service_lookup.get(normalized_command, normalized_command)
    if service_name in SERVICE_COMMANDS:
        help_text = SERVICE_COMMANDS.get(service_name, {}).get("help")
        print(f"'{service_name}' is a host-only service command.")
        if isinstance(help_text, str) and help_text.strip():
            print(help_text)
        print(f"Run it from the host wrapper: ./zde {service_name}")
        return 0

    redirected = COMMAND_REDIRECTS.get(normalized_command)
    prepend_args: list[str] = []
    if redirected is not None:
        command_name = redirected[0]
        prepend_args = list(redirected[1])
    module_name = command_to_module_name(command_name)
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
