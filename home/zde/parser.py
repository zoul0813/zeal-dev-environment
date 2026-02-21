from __future__ import annotations

import argparse
from types import ModuleType

from mods.commands import (
    DEFAULT_MODULE_ALIASES,
    discover_command_modules,
    discover_subcommands,
    import_command_module,
    module_name_to_command,
)


def _configure_module_parser(module: ModuleType, parser: argparse.ArgumentParser, module_name: str) -> None:
    custom = getattr(module, "configure_parser", None)
    if callable(custom):
        custom(parser)
        return

    subcommands = sorted(discover_subcommands(module).keys())
    if subcommands:
        sub = parser.add_subparsers(dest=f"{module_name}_subcommand")
        for subcommand in subcommands:
            sub_p = sub.add_parser(subcommand)
            sub_p.add_argument("args", nargs=argparse.REMAINDER)
        return

    parser.add_argument("args", nargs=argparse.REMAINDER)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zde")
    sub = parser.add_subparsers(dest="command")

    for module_name in discover_command_modules():
        module = import_command_module(module_name)
        command_name = module_name_to_command(module_name)
        aliases = DEFAULT_MODULE_ALIASES.get(module_name, [])
        cmd_parser = sub.add_parser(command_name, aliases=aliases)
        _configure_module_parser(module, cmd_parser, module_name)

    return parser
