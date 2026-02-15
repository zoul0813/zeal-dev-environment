from __future__ import annotations

import shutil
from datetime import datetime, timezone

from mods.update import (
    build_lock_entry,
    clone_repo,
    configured_ref,
    current_commit,
    load_deps_yaml,
    load_lock,
    order_deps_by_dependency,
    resolve_dep_path,
    resolve_env,
    update_repo,
    write_lock,
)


def _deps_by_id() -> tuple[dict[str, dict], object]:
    env = resolve_env()
    deps = order_deps_by_dependency(load_deps_yaml(env.deps_file))
    dep_map = {dep["id"]: dep for dep in deps}
    return dep_map, env


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
    return dep_path.is_dir() and (dep_path / ".git").exists()


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


def subcmd_list(args: list[str]) -> int:
    dep_map, env = _deps_by_id()
    lock = load_lock(env.lock_file)
    lock_deps = lock.get("dependencies", {})

    print("ID                               REQUIRED  INSTALLED  TRACKED")
    for dep_id in sorted(dep_map.keys()):
        dep = dep_map[dep_id]
        required = bool(dep.get("required", False))
        dep_path = resolve_dep_path(env, dep["path"])
        installed = _is_git_repo(dep_path)
        tracked = dep_id in lock_deps
        print(f"{dep_id:<32}  {'yes' if required else 'no ':<8}  {'yes' if installed else 'no ':<9}  {'yes' if tracked else 'no'}")
    return 0


def subcmd_install(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps install <id>")
        return 1

    dep_id = args[0]
    dep_map, env = _deps_by_id()
    target_dep = dep_map.get(dep_id)
    if target_dep is None:
        print(f"Unknown dependency id: {dep_id}")
        return 1

    if bool(target_dep.get("required", False)):
        print(f"Dependency is required and managed by update: {dep_id}")
        return 1

    install_ids = _dependency_chain(dep_map, dep_id)
    for install_id in install_ids:
        dep = dep_map[install_id]
        dep_path = resolve_dep_path(env, dep["path"])
        has_git = _is_git_repo(dep_path)
        ref_type, ref_value = configured_ref(dep)

        if dep_path.exists() and not has_git:
            try:
                has_entries = next(dep_path.iterdir(), None) is not None
            except OSError:
                has_entries = True
            if has_entries:
                print(f"Dependency path exists but is not a git repo: {dep_path}")
                return 1

        if not has_git:
            rc = clone_repo(dep_path, dep["repo"], ref_type, ref_value)
        else:
            rc = update_repo(dep_path, dep["repo"], ref_type, ref_value)

        if rc != 0:
            print(f"Failed installing dependency: {install_id}")
            return rc

        _write_dep_lock_entry(env, install_id, dep, "synced")
        print(f"Installed dependency: {install_id}")
    return 0


def subcmd_remove(args: list[str]) -> int:
    if not args:
        print("Usage: zde deps remove <id>")
        return 1

    dep_id = args[0]
    dep_map, env = _deps_by_id()
    dep = dep_map.get(dep_id)
    if dep is None:
        print(f"Unknown dependency id: {dep_id}")
        return 1

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


def help() -> int:
    print("Usage: zde deps <subcommand> [args]")
    print("Subcommands:")
    print("  list")
    print("  install <id>")
    print("  remove <id>")
    return 0


def main(args: list[str]) -> int:
    return subcmd_list(args)
