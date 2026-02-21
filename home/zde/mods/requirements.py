from __future__ import annotations

import sys
from datetime import datetime, timezone

from mods.depbuild import run_dep_build
from mods.update import (
    build_lock_entry,
    clone_repo,
    configured_ref,
    current_commit,
    is_git_repo,
    load_deps_yaml,
    load_lock,
    resolve_dep_path,
    resolve_env,
    write_lock,
)


def _deps_by_id() -> dict[str, dict]:
    env = resolve_env()
    deps = load_deps_yaml(env.deps_file)
    return {dep["id"]: dep for dep in deps}


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


def _find_missing(required_dep_ids: list[str]) -> list[str]:
    env = resolve_env()
    dep_map = _deps_by_id()
    dep_ids = set(dep_map.keys())

    missing: list[str] = []
    for dep_id in required_dep_ids:
        if dep_id not in dep_ids:
            print(f"Warning: command requires unknown dep id: {dep_id}")
            missing.append(dep_id)
            continue
        dep = dep_map[dep_id]
        dep_path = resolve_dep_path(env, dep["path"])
        if not is_git_repo(dep_path):
            missing.append(dep_id)
    return missing


def _print_missing(missing: list[str]) -> None:
    dep_map = _deps_by_id()
    required_missing = [dep_id for dep_id in missing if bool(dep_map.get(dep_id, {}).get("required", False))]
    optional_missing = [dep_id for dep_id in missing if dep_id not in required_missing]

    print("Missing required dependencies for this command:")
    for dep_id in missing:
        print(f"  - {dep_id}")
    if required_missing:
        print("Install/sync required dependencies with:")
        print("  zde update")
    if optional_missing:
        print("Install optional dependencies with:")
        for dep_id in optional_missing:
            print(f"  zde deps install \"{dep_id}\"")


def _install_missing(missing: list[str]) -> bool:
    env = resolve_env()
    dep_map = _deps_by_id()
    lock = load_lock(env.lock_file)
    lock_deps = lock.setdefault("dependencies", {})
    if not isinstance(lock_deps, dict):
        lock_deps = {}
        lock["dependencies"] = lock_deps

    # Install only missing deps and their missing dependency chain.
    install_ids: list[str] = []
    seen: set[str] = set()
    for dep_id in missing:
        for chain_id in _dependency_chain(dep_map, dep_id):
            if chain_id in seen:
                continue
            chain_dep = dep_map.get(chain_id)
            if chain_dep is None:
                continue
            chain_path = resolve_dep_path(env, chain_dep["path"])
            if is_git_repo(chain_path):
                continue
            seen.add(chain_id)
            install_ids.append(chain_id)

    for dep_id in install_ids:
        dep = dep_map[dep_id]
        dep_path = resolve_dep_path(env, dep["path"])
        ref_type, ref_value = configured_ref(dep)
        has_git = is_git_repo(dep_path)

        if dep_path.exists() and not has_git:
            try:
                has_entries = next(dep_path.iterdir(), None) is not None
            except OSError:
                has_entries = True
            if has_entries:
                print(f"Dependency path exists but is not a git repo: {dep_path}")
                return False

        if not has_git:
            rc = clone_repo(dep_path, dep["repo"], ref_type, ref_value)
            if rc != 0:
                print(f"Failed installing dependency: {dep_id}")
                return False

        rc = run_dep_build(dep, dep_path)
        if rc != 0:
            print(f"Failed building dependency: {dep_id}")
            return False

        now = datetime.now(timezone.utc).isoformat()
        lock_deps[dep_id] = build_lock_entry(
            dep=dep,
            ref_type=ref_type,
            ref_value=ref_value,
            status="synced",
            updated_at=now,
            current_commit_value=current_commit(dep_path),
        )
        lock["updated_at"] = now
        write_lock(env.lock_file, lock)

    return True


def require_deps(required_dep_ids: list[str]) -> bool:
    if not required_dep_ids:
        return True

    missing = _find_missing(required_dep_ids)

    if not missing:
        return True

    _print_missing(missing)

    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False

    reply = input("Install/sync missing required dependencies now and continue? ([Y]es, [N]o) ").strip().lower()
    if reply not in {"y", "yes"}:
        return False

    if not _install_missing(missing):
        return False

    missing = _find_missing(required_dep_ids)
    if not missing:
        return True

    print("Dependencies are still missing after install/sync:")
    for dep_id in missing:
        print(f"  - {dep_id}")
    return False
