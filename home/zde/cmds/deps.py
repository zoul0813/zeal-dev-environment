from __future__ import annotations

import os
import sys

from mods.deps import DepCatalog
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
        "red": "\033[31m",
        "yellow": "\033[33m",
        "green": "\033[32m",
    }
    return f"{codes[color]}{text}\033[0m"


def subcmd_list(args: list[str]) -> int:
    catalog = DepCatalog()
    use_color = _colors_enabled()
    deps = catalog.deps

    if len(args) > 1:
        print("Usage: zde deps list [category]")
        return 1
    if args:
        category = args[0]
        deps = catalog.deps_for_category(category)
        if not deps:
            available = ", ".join(catalog.categories)
            print(f"Unknown category: {category}")
            print(f"Available categories: {available}")
            return 1

    mark_w = 3
    id_w = 36
    state_w = 20
    track_w = 7
    print(f"{'[?]':<{mark_w}} {'ID':<{id_w}} {'STATE':<{state_w}} {'TRACKED':<{track_w}} ALIASES")
    for dep in deps:
        track_s = "yes" if dep.tracked else "no"
        alias_text = ", ".join(dep.aliases) if dep.aliases else "-"
        id_text = dep.id + (" *" if dep.required else "")

        state_plain = dep.state
        state_cell = state_plain.ljust(state_w)
        row = f"{dep.marker:<{mark_w}} {id_text:<{id_w}} {state_cell} {track_s:<{track_w}} {alias_text}"

        if dep.required and not dep.installed:
            print(_paint(row, "red", use_color))
        elif dep.installed and dep.missing_dependency_ids:
            print(_paint(row, "yellow", use_color))
        elif dep.installed and not dep.tracked:
            print(_paint(row, "yellow", use_color))
        elif dep.installed:
            print(_paint(row, "green", use_color))
        else:
            print(row)
    return 0


def subcmd_cats(args: list[str]) -> int:
    catalog = DepCatalog()
    for category in catalog.categories:
        print(category)
    return 0


def subcmd_install(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps install <id>")
        return 1

    raw_id = args[0]
    catalog = DepCatalog()
    try:
        dep = catalog.resolve(raw_id)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if dep is None:
        print(f"Unknown dependency id: {raw_id}")
        return 1

    return dep.install()


def subcmd_update(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps update <id>")
        return 1

    raw_id = args[0]
    catalog = DepCatalog()
    try:
        dep = catalog.resolve(raw_id)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if dep is None:
        print(f"Unknown dependency id: {raw_id}")
        return 1

    return dep.update()


def subcmd_remove(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps remove <id>")
        return 1

    raw_id = args[0]
    catalog = DepCatalog()
    try:
        dep = catalog.resolve(raw_id)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if dep is None:
        print(f"Unknown dependency id: {raw_id}")
        return 1

    return dep.remove()


def subcmd_info(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps info <id>")
        return 1

    raw_id = args[0]
    catalog = DepCatalog()
    try:
        dep = catalog.resolve(raw_id)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if dep is None:
        print(f"Unknown dependency id: {raw_id}")
        return 1

    print(dep.render_info())
    return 0


def subcmd_build(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps build <id>")
        return 1

    raw_id = args[0]
    catalog = DepCatalog()
    try:
        dep = catalog.resolve(raw_id)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if dep is None:
        print(f"Unknown dependency id: {raw_id}")
        return 1

    return dep.build()


def help() -> int:
    print("Usage: zde deps <subcommand> [args]")
    print("Subcommands:")
    print("  list [category]")
    print("  cats")
    print("  install <id>")
    print("  update <id>")
    print("  info <id>")
    print("  build <id>")
    print("  remove <id>")
    return 0


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="deps",
        label="deps",
        help="Dependency management",
        actions=[
            ActionSpec(id="open", label="open", help="Open dependency manager screen"),
        ],
    )


def get_tui_screen():
    from scrns.deps_menu import DepsMenuScreen

    return DepsMenuScreen()


def main(args: list[str]) -> int:
    if args:
        return subcmd_list(args)

    help()
    print()
    return subcmd_list([])
