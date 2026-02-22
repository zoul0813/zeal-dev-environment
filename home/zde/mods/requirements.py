from __future__ import annotations

import sys

from mods.deps import DepCatalog


def _find_missing(required_dep_ids: list[str]) -> list[str]:
    catalog = DepCatalog()

    missing: list[str] = []
    for dep_id in required_dep_ids:
        dep = catalog.get(dep_id)
        if dep is None:
            print(f"Warning: command requires unknown dep id: {dep_id}")
            missing.append(dep_id)
            continue
        if not dep.installed:
            missing.append(dep_id)
    return missing


def _print_missing(missing: list[str]) -> None:
    catalog = DepCatalog()
    required_missing: list[str] = []
    optional_missing: list[str] = []

    for dep_id in missing:
        dep = catalog.get(dep_id)
        if dep is not None and dep.required:
            required_missing.append(dep_id)
        else:
            optional_missing.append(dep_id)

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
    catalog = DepCatalog()

    # Install only missing deps and their missing dependency chain.
    install_ids: list[str] = []
    seen: set[str] = set()
    for dep_id in missing:
        if catalog.get(dep_id) is None:
            continue
        for chain_id in catalog.dependency_chain(dep_id):
            if chain_id in seen:
                continue
            chain_dep = catalog.get(chain_id)
            if chain_dep is None or chain_dep.installed:
                continue
            seen.add(chain_id)
            install_ids.append(chain_id)

    for dep_id in install_ids:
        rc = catalog.install_dep(dep_id, allow_required=True, include_dependencies=False)
        if rc != 0:
            return False

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
