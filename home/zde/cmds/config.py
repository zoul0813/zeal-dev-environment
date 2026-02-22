from __future__ import annotations

import os
import sys

from mods.config import CONFIG_FILE, Config, ConfigOption
from mods.tui.contract import ActionSpec, CommandSpec


def _colors_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    return sys.stdout.isatty()


def _paint(text: str, color: str, enabled: bool) -> str:
    if not enabled:
        return text
    codes = {
        "white": "\033[37m",
        "yellow": "\033[33m",
        "green": "\033[32m",
    }
    return f"{codes[color]}{text}\033[0m"


def _format_value(option: ConfigOption, value: object) -> str:
    if option.value_type == "bool":
        return "on" if bool(value) else "off"
    return str(value)


def _render_grouped_yaml(config: Config) -> list[str]:
    tree: dict[str, object] = {}
    use_color = _colors_enabled()

    for option in Config.iter_options():
        value, explicit = config.get_with_source(option.key)
        value_text = _format_value(option, value)
        if not explicit:
            display = _paint(value_text, "white", use_color)
        elif option.value_type == "bool":
            display = _paint(value_text, "green" if bool(value) else "yellow", use_color)
        else:
            display = _paint(value_text, "green", use_color)

        current = tree
        for part in option.path[:-1]:
            child = current.get(part)
            if not isinstance(child, dict):
                child = {}
                current[part] = child
            current = child
        current[option.path[-1]] = display

    lines: list[str] = []

    def emit(node: dict[str, object], indent: int) -> None:
        for name in sorted(node.keys()):
            value = node[name]
            prefix = "  " * indent
            if isinstance(value, dict):
                lines.append(f"{prefix}{name}:")
                emit(value, indent + 1)
            else:
                lines.append(f"{prefix}{name}: {value}")

    emit(tree, 0)
    return lines


def subcmd_list(args: list[str]) -> int:
    config = Config.load()
    print(f"Config file: {CONFIG_FILE}")
    for line in _render_grouped_yaml(config):
        print(line)
    return 0


def subcmd_get(args: list[str]) -> int:
    if len(args) != 1:
        print("Usage: zde config get <key>")
        return 1
    option = Config.resolve_option(args[0])
    if option is None:
        print(f"Unknown config key: {args[0]}")
        return 1
    config = Config.load()
    value = config.get(option.key)
    print(_format_value(option, value))
    return 0


def subcmd_set(args: list[str]) -> int:
    if len(args) != 2:
        print("Usage: zde config set <key> <value>")
        return 1

    option = Config.resolve_option(args[0])
    if option is None:
        print(f"Unknown config key: {args[0]}")
        return 1

    config = Config.load()
    try:
        value = config.set_from_text(option.key, args[1])
    except ValueError as exc:
        print(str(exc))
        return 1
    config.save()
    print(f"{option.key}: {_format_value(option, value)}")
    return 0


def subcmd_unset(args: list[str]) -> int:
    if len(args) != 1:
        print("Usage: zde config unset <key>")
        return 1

    option = Config.resolve_option(args[0])
    if option is None:
        print(f"Unknown config key: {args[0]}")
        return 1

    config = Config.load()
    config.unset(option.key)
    config.save()
    value = config.get(option.key)
    print(f"{option.key}: {_format_value(option, value)}")
    return 0


def help() -> int:
    print("Usage: zde config <subcommand> [args]")
    print("Subcommands:")
    print("  list")
    print("  get <key>")
    print("  set <key> <value>")
    print("  unset <key>")
    print("Keys:")
    for option in Config.iter_options():
        print(f"  {option.key} - {option.description}")
    return 0


def main(args: list[str]) -> int:
    if not args:
        return subcmd_list([])
    subcmd = args[0].strip().lower()
    subargs = args[1:]
    if subcmd == "list":
        return subcmd_list(subargs)
    if subcmd == "get":
        return subcmd_get(subargs)
    if subcmd == "set":
        return subcmd_set(subargs)
    if subcmd == "unset":
        return subcmd_unset(subargs)
    if subcmd in {"help", "-h", "--help"}:
        return help()
    print(f"Unknown subcommand: {subcmd}")
    return help()


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="config",
        label="config",
        help="View and edit ZDE configuration",
        actions=[
            ActionSpec(id="open", label="open", help="Open config editor screen"),
        ],
    )


def get_tui_screen():
    from mods.tui.screens.config_menu import ConfigMenuScreen

    return ConfigMenuScreen()
