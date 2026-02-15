from __future__ import annotations

from mods.update import load_deps_yaml, load_lock, resolve_env


def require_deps(required_dep_ids: list[str]) -> bool:
    if not required_dep_ids:
        return True

    env = resolve_env()
    deps = load_deps_yaml(env.deps_file)
    dep_ids = {dep["id"] for dep in deps}
    lock = load_lock(env.lock_file)
    installed = lock.get("dependencies", {})
    if not isinstance(installed, dict):
        installed = {}

    missing: list[str] = []
    for dep_id in required_dep_ids:
        if dep_id not in dep_ids:
            print(f"Warning: command requires unknown dep id: {dep_id}")
            missing.append(dep_id)
            continue
        if dep_id not in installed:
            missing.append(dep_id)

    if not missing:
        return True

    print("Missing required dependencies for this command:")
    for dep_id in missing:
        print(f"  - {dep_id}")
    print("Install with:")
    for dep_id in missing:
        print(f"  zde deps install \"{dep_id}\"")
    return False

