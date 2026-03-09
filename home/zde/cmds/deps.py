from __future__ import annotations

from mods.cli import paint
from mods.deps import DepCatalog
from mods import image as image_mod
from mods.tui.contract import ActionSpec, CommandSpec


def _print_dep_rows(deps) -> None:
    mark_w = 3
    id_w = 36
    state_w = 20
    print(f"{'[?]':<{mark_w}} {'ID':<{id_w}} {'STATE':<{state_w}} ALIASES")
    for dep in deps:
        alias_text = ", ".join(dep.aliases) if dep.aliases else "-"
        id_text = dep.id + (" *" if dep.required else "")

        state_plain = dep.state
        state_cell = state_plain.ljust(state_w)
        row = f"{dep.marker:<{mark_w}} {id_text:<{id_w}} {state_cell} {alias_text}"

        if dep.required and not dep.installed:
            print(paint(row, "red"))
        elif dep.installed and dep.missing_dependency_ids:
            print(paint(row, "yellow"))
        elif dep.installed and not dep.tracked:
            print(paint(row, "yellow"))
        elif dep.installed:
            print(paint(row, "green"))
        else:
            print(row)


def subcmd_list(args: list[str]) -> int:
    catalog = DepCatalog()
    deps = catalog.deps

    if len(args) > 1:
        print("Usage: zde deps list [category]")
        return 1
    if args:
        category = args[0]
        deps = catalog.category(category)
        if not deps:
            available = ", ".join(catalog.categories)
            print(f"Unknown category: {category}")
            print(f"Available categories: {available}")
            return 1

    _print_dep_rows(deps)
    return 0


def _print_installed_summary() -> int:
    catalog = DepCatalog()
    deps = catalog.installed()
    _print_dep_rows(deps)
    return 0


def subcmd_cats(args: list[str]) -> int:
    catalog = DepCatalog()
    for category in catalog.categories:
        print(category)
    return 0


def _resolve_dep_ids(args: list[str], usage: str) -> tuple[DepCatalog | None, list[str] | None, int]:
    if not args:
        print(usage)
        return None, None, 1

    catalog = DepCatalog()
    dep_ids: list[str] = []
    seen: set[str] = set()

    for raw_id in args:
        try:
            dep = catalog.resolve(raw_id)
        except RuntimeError as exc:
            print(str(exc))
            return None, None, 1
        if dep is None:
            print(f"Unknown dependency id: {raw_id}")
            return None, None, 1
        if dep.id in seen:
            continue
        dep_ids.append(dep.id)
        seen.add(dep.id)

    return catalog, dep_ids, 0


def subcmd_install(args: list[str]) -> int:
    catalog, dep_ids, rc = _resolve_dep_ids(args, "Usage: zde deps install <id> [id...]")
    if rc != 0 or catalog is None or dep_ids is None:
        return rc

    for dep_id in dep_ids:
        rc = catalog.install_dep(dep_id)
        if rc != 0:
            return rc
    return 0


def subcmd_update(args: list[str]) -> int:
    catalog, dep_ids, rc = _resolve_dep_ids(args, "Usage: zde deps update <id> [id...]")
    if rc != 0 or catalog is None or dep_ids is None:
        return rc

    for dep_id in dep_ids:
        rc = catalog.update_dep(dep_id)
        if rc != 0:
            return rc
    return 0


def subcmd_remove(args: list[str]) -> int:
    catalog, dep_ids, rc = _resolve_dep_ids(args, "Usage: zde deps remove <id> [id...]")
    if rc != 0 or catalog is None or dep_ids is None:
        return rc

    for dep_id in dep_ids:
        rc = catalog.remove_dep(dep_id)
        if rc != 0:
            return rc
    return 0


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
    catalog, dep_ids, rc = _resolve_dep_ids(args, "Usage: zde deps build <id> [id...]")
    if rc != 0 or catalog is None or dep_ids is None:
        return rc

    for dep_id in dep_ids:
        rc = catalog.build_dep(dep_id)
        if rc != 0:
            return rc
    return 0


def subcmd_stage(args: list[str]) -> int:
    if len(args) < 2:
        print("Usage: zde deps stage <target> <id> [id...]")
        return 1

    target = args[0]
    try:
        image = image_mod.get_image(target.strip().lower())
    except ValueError:
        supported = ", ".join(sorted(img.image_type for img in image_mod.images()))
        print(f"Target must be one of: {supported}")
        return 1

    catalog, dep_ids, rc = _resolve_dep_ids(args[1:], "Usage: zde deps stage <target> <id> [id...]")
    if rc != 0 or catalog is None or dep_ids is None:
        return rc

    for dep_id in dep_ids:
        dep = catalog.get(dep_id)
        if dep is None:
            print(f"Unknown dependency id: {dep_id}")
            return 1
        rc = dep.stage(image)
        if rc != 0:
            return rc
    return 0


def help() -> int:
    print("Usage: zde deps <subcommand> [args]")
    print("Subcommands:")
    print("  list [category]")
    print("  cats")
    print("  install <id> [id...]")
    print("  update <id> [id...]")
    print("  info <id>")
    print("  build <id> [id...]")
    print("  stage <target> <id> [id...]")
    print("  remove <id> [id...]")
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
    return _print_installed_summary()
