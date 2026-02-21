from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable
from types import ModuleType

import cmds


DEFAULT_MODULE_ALIASES: dict[str, list[str]] = {
    "emulator": ["emu"],
}


def discover_command_modules() -> list[str]:
    names: list[str] = []
    for mod in pkgutil.iter_modules(cmds.__path__):
        name = mod.name
        if name.startswith("_"):
            continue
        names.append(name)
    return sorted(names)


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


def module_name_to_command(module_name: str) -> str:
    return module_name.replace("_", "-")


def build_alias_lookup(module_aliases: dict[str, list[str]]) -> dict[str, str]:
    alias_lookup: dict[str, str] = {}
    for module_name, aliases in module_aliases.items():
        for alias in aliases:
            alias_lookup[alias.replace("-", "_")] = module_name
    return alias_lookup


def command_to_module_name(command_name: str, module_aliases: dict[str, list[str]]) -> str:
    alias_lookup = build_alias_lookup(module_aliases)
    normalized = command_name.replace("-", "_")
    return alias_lookup.get(normalized, normalized)


def import_command_module(module_name: str) -> ModuleType:
    return importlib.import_module(f"cmds.{module_name}")
