from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime, timezone

from mods.depbuild import run_dep_build
from mods.migrate import migrate_broken_submodule_checkout
from mods.requirements import require_deps
from mods.tui.contract import ActionSpec, CommandSpec
from mods.update import (
    build_lock_entry,
    clone_repo,
    configured_ref,
    current_commit,
    is_git_repo,
    load_deps_yaml,
    load_lock,
    order_deps_by_dependency,
    resolve_dep_path,
    resolve_env,
    write_lock,
)


def _deps_by_id() -> tuple[dict[str, dict], object]:
    env = resolve_env()
    deps = order_deps_by_dependency(load_deps_yaml(env.deps_file))
    dep_map = {dep["id"]: dep for dep in deps}
    return dep_map, env


def _repo_name_from_id(dep_id: str) -> str:
    if "/" in dep_id:
        return dep_id.split("/", 1)[1]
    return dep_id


def _lookup_dep(dep_map: dict[str, dict], raw_id: str) -> tuple[str, dict] | None:
    if raw_id in dep_map:
        return raw_id, dep_map[raw_id]

    wanted = raw_id.casefold()
    matches: list[tuple[str, dict]] = []
    for dep_id, dep in dep_map.items():
        if dep_id.casefold() == wanted:
            matches.append((dep_id, dep))
        for alias in dep.get("aliases", []):
            if alias.casefold() == wanted:
                matches.append((dep_id, dep))
        if _repo_name_from_id(dep_id).casefold() == wanted:
            matches.append((dep_id, dep))

    # Deduplicate by canonical dependency ID.
    by_id: dict[str, dict] = {}
    for dep_id, dep in matches:
        by_id[dep_id] = dep

    if len(by_id) == 0:
        return None
    if len(by_id) > 1:
        choices = ", ".join(sorted(by_id.keys()))
        raise RuntimeError(f"Ambiguous dependency identifier '{raw_id}'. Matches: {choices}")
    dep_id, dep = next(iter(by_id.items()))
    return dep_id, dep


def _dependency_chain(dep_map: dict[str, dict], dep_id: str) -> list[str]:
    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[str] = []

    def visit(cur: str) -> None:
        if cur in visited:
            return
        if cur in visiting:
            raise RuntimeError(f"Dependency cycle detected at '{cur}'")
        dep = dep_map.get(cur)
        if dep is None:
            raise RuntimeError(f"Unknown dependency id in chain: {cur}")
        visiting.add(cur)
        for parent in dep.get("depends_on", []):
            visit(parent)
        visiting.remove(cur)
        visited.add(cur)
        ordered.append(cur)

    visit(dep_id)
    return ordered


def _is_git_repo(dep_path) -> bool:
    return is_git_repo(dep_path)


def _write_dep_lock_entry(env, dep_id: str, dep: dict, status: str) -> None:
    lock = load_lock(env.lock_file)
    lock_deps = lock.setdefault("dependencies", {})
    now = datetime.now(timezone.utc).isoformat()
    ref_type, ref_value = configured_ref(dep)
    dep_path = resolve_dep_path(env, dep["path"])
    lock_deps[dep_id] = build_lock_entry(
        dep=dep,
        ref_type=ref_type,
        ref_value=ref_value,
        status=status,
        updated_at=now,
        current_commit_value=current_commit(dep_path),
    )
    lock["updated_at"] = now
    write_lock(env.lock_file, lock)


def _remove_dep_lock_entry(env, dep_id: str) -> None:
    lock = load_lock(env.lock_file)
    lock_deps = lock.setdefault("dependencies", {})
    if dep_id in lock_deps:
        del lock_deps[dep_id]
    lock["updated_at"] = datetime.now(timezone.utc).isoformat()
    write_lock(env.lock_file, lock)


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


def _preferred_dep_label(dep: dict) -> str:
    aliases = dep.get("aliases", [])
    if isinstance(aliases, list) and aliases:
        return aliases[0]
    return dep["id"]


def subcmd_list(args: list[str]) -> int:
    dep_map, env = _deps_by_id()
    lock = load_lock(env.lock_file)
    lock_deps = lock.get("dependencies", {})
    use_color = _colors_enabled()

    installed_by_id: dict[str, bool] = {}
    for dep_id, dep in dep_map.items():
        dep_path = resolve_dep_path(env, dep["path"])
        installed_by_id[dep_id] = _is_git_repo(dep_path)

    mark_w = 3
    id_w = 34
    state_w = 12
    req_w = 8
    track_w = 7
    print(f"{'[?]':<{mark_w}} {'ID':<{id_w}} {'STATE':<{state_w}} {'REQUIRED':<{req_w}} {'TRACKED':<{track_w}} ALIASES")
    for dep_id in sorted(dep_map.keys()):
        dep = dep_map[dep_id]
        required = bool(dep.get("required", False))
        installed = installed_by_id[dep_id]
        tracked = dep_id in lock_deps
        missing_deps = [parent for parent in dep.get("depends_on", []) if not installed_by_id.get(parent, False)]
        aliases = dep.get("aliases", [])
        alias_text = ", ".join(aliases) if isinstance(aliases, list) and aliases else "-"
        req_s = "yes" if required else "no"
        track_s = "yes" if tracked else "no"
        inst_mark = "[x]" if installed else "[ ]"
        if required and not installed:
            state_plain = "required-miss"
            state_colored = state_plain
        elif installed and missing_deps:
            labels = [_preferred_dep_label(dep_map[parent]) for parent in missing_deps if parent in dep_map]
            if labels:
                label_text = ",".join(labels)
                state_plain = f"broken({label_text})"
                state_colored = state_plain
                if use_color:
                    state_colored = state_colored.replace(label_text, _paint(label_text, "yellow", True), 1)
            else:
                state_plain = "broken-deps"
                state_colored = state_plain
        elif installed and not tracked:
            state_plain = "untracked"
            state_colored = state_plain
        elif installed:
            state_plain = "ok"
            state_colored = state_plain
        else:
            state_plain = "-"
            state_colored = state_plain

        state_cell = state_plain.ljust(state_w)
        if use_color and state_colored != state_plain:
            state_cell = state_cell.replace(state_plain, state_colored, 1)

        row = f"{inst_mark:<{mark_w}} {dep_id:<{id_w}} {state_cell} {req_s:<{req_w}} {track_s:<{track_w}} {alias_text}"

        if required and not installed:
            print(_paint(row, "red", use_color))
        elif installed and missing_deps:
            print(row)
        elif installed and not tracked:
            print(_paint(row, "yellow", use_color))
        elif installed:
            print(_paint(row, "green", use_color))
        else:
            print(row)
    return 0


def subcmd_install(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps install <id>")
        return 1

    raw_id = args[0]
    dep_map, env = _deps_by_id()
    try:
        resolved = _lookup_dep(dep_map, raw_id)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if resolved is None:
        print(f"Unknown dependency id: {raw_id}")
        return 1
    dep_id, target_dep = resolved

    if bool(target_dep.get("required", False)):
        print(f"Dependency is required and managed by update: {dep_id}")
        return 1

    install_ids = _dependency_chain(dep_map, dep_id)
    for install_id in install_ids:
        dep = dep_map[install_id]
        dep_path = resolve_dep_path(env, dep["path"])
        has_git = _is_git_repo(dep_path)
        if not has_git and dep_path.exists():
            migrated = migrate_broken_submodule_checkout(dep_path, True)
            if migrated:
                has_git = False
        ref_type, ref_value = configured_ref(dep)

        if dep_path.exists() and not has_git:
            try:
                has_entries = next(dep_path.iterdir(), None) is not None
            except OSError:
                has_entries = True
            if has_entries:
                print(f"Dependency path exists but is not a git repo: {dep_path}")
                return 1

        if has_git:
            _write_dep_lock_entry(env, install_id, dep, "synced")
            print(f"Dependency already installed: {install_id}")
            continue

        rc = clone_repo(dep_path, dep["repo"], ref_type, ref_value)

        if rc != 0:
            print(f"Failed installing dependency: {install_id}")
            return rc

        rc = run_dep_build(dep, dep_path)
        if rc != 0:
            _write_dep_lock_entry(env, install_id, dep, "build_failed")
            print(f"Failed building dependency: {install_id}")
            return rc

        _write_dep_lock_entry(env, install_id, dep, "synced")
        print(f"Installed dependency: {install_id}")
    return 0


def subcmd_remove(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps remove <id>")
        return 1

    raw_id = args[0]
    dep_map, env = _deps_by_id()
    try:
        resolved = _lookup_dep(dep_map, raw_id)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if resolved is None:
        print(f"Unknown dependency id: {raw_id}")
        return 1
    dep_id, dep = resolved

    if bool(dep.get("required", False)):
        print(f"Cannot remove required dependency: {dep_id}")
        return 1

    dep_path = resolve_dep_path(env, dep["path"])
    if dep_path.exists():
        if dep_path.is_dir():
            shutil.rmtree(dep_path)
        else:
            dep_path.unlink()

    _remove_dep_lock_entry(env, dep_id)
    print(f"Removed dependency: {dep_id}")
    return 0


def subcmd_info(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps info <id>")
        return 1

    raw_id = args[0]
    dep_map, env = _deps_by_id()
    try:
        resolved = _lookup_dep(dep_map, raw_id)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if resolved is None:
        print(f"Unknown dependency id: {raw_id}")
        return 1

    def _pretty_label(key: str) -> str:
        return key.replace("_", " ").title()

    def _print_value(value, indent: str = "  ") -> None:
        if isinstance(value, list):
            if not value:
                print(f"{indent}-")
                return
            for item in value:
                if isinstance(item, (list, dict)):
                    print(f"{indent}-")
                    _print_value(item, indent + "  ")
                else:
                    print(f"{indent}- {item}")
            return
        if isinstance(value, dict):
            if not value:
                print(f"{indent}-")
                return
            for k in sorted(value.keys()):
                v = value[k]
                if isinstance(v, (list, dict)):
                    print(f"{indent}{_pretty_label(str(k))}:")
                    _print_value(v, indent + "  ")
                else:
                    print(f"{indent}{_pretty_label(str(k))}: {v}")
            return
        print(f"{indent}{value}")

    dep_id, dep = resolved
    dep_path = resolve_dep_path(env, dep["path"])
    installed = _is_git_repo(dep_path)
    lock = load_lock(env.lock_file)
    lock_deps = lock.get("dependencies", {})
    tracked = dep_id in lock_deps
    print(f"Id: {dep_id}")
    print(f"Installed: {'yes' if installed else 'no'}")
    print(f"Tracked: {'yes' if tracked else 'no'}")
    for key in sorted(dep.keys()):
        if key == "id":
            continue
        label = _pretty_label(key)
        value = dep[key]
        if isinstance(value, (dict, list)):
            print(f"{label}:")
            _print_value(value)
            continue
        print(f"{label}: {value}")

    return 0


def subcmd_build(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps build <id>")
        return 1

    raw_id = args[0]
    dep_map, env = _deps_by_id()
    try:
        resolved = _lookup_dep(dep_map, raw_id)
    except RuntimeError as exc:
        print(str(exc))
        return 1
    if resolved is None:
        print(f"Unknown dependency id: {raw_id}")
        return 1
    dep_id, dep = resolved

    needed_ids = [dep_id, *dep.get("depends_on", [])]
    if not require_deps(needed_ids):
        return 1

    dep_path = resolve_dep_path(env, dep["path"])
    if not _is_git_repo(dep_path):
        print(f"Dependency not installed: {dep_id}")
        return 1

    if not isinstance(dep.get("build"), dict):
        print(f"No build configured for dependency: {dep_id}")
        _write_dep_lock_entry(env, dep_id, dep, "synced")
        return 0

    rc = run_dep_build(dep, dep_path)
    if rc != 0:
        _write_dep_lock_entry(env, dep_id, dep, "build_failed")
        print(f"Failed building dependency: {dep_id}")
        return rc

    _write_dep_lock_entry(env, dep_id, dep, "synced")
    print(f"Built dependency: {dep_id}")
    return 0


def help() -> int:
    print("Usage: zde deps <subcommand> [args]")
    print("Subcommands:")
    print("  list")
    print("  install <id>")
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
    from mods.tui.screens.deps_menu import DepsMenuScreen

    return DepsMenuScreen()


def main(args: list[str]) -> int:
    if args:
        return subcmd_list(args)

    help()
    print()
    return subcmd_list([])
