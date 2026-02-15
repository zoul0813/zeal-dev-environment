from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


def broken_submodule_gitdir(path: Path) -> Path | None:
    git_marker = path / ".git"
    if not git_marker.is_file():
        return None
    try:
        first = git_marker.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    prefix = "gitdir:"
    if not first.lower().startswith(prefix):
        return None
    raw = first[len(prefix) :].strip()
    if not raw:
        return None
    target = (path / raw).resolve() if not Path(raw).is_absolute() else Path(raw)
    if ".git/modules/" not in str(target):
        return None
    if target.exists():
        return None
    return target


def has_legacy_submodules(
    deps: list[dict],
    resolve_dep_path: Callable[[str], Path],
) -> bool:
    for dep in deps:
        dep_path = resolve_dep_path(dep["path"])
        if not dep_path.exists():
            continue
        if broken_submodule_gitdir(dep_path) is not None:
            return True
    return False


def migrate_broken_submodule_checkout(path: Path, migrate_enabled: bool) -> Path | None:
    missing_target = broken_submodule_gitdir(path)
    if missing_target is None:
        return None

    if migrate_enabled:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
        backup_root = path.parent / "backup" / "migrate"
        backup_root.mkdir(parents=True, exist_ok=True)
        backup = backup_root / f"{path.name}.zde-backup-{ts}"
        shutil.move(str(path), str(backup))
        print(
            f"Detected broken legacy submodule checkout at {path}; moved to {backup} "
            f"(missing gitdir: {missing_target})"
        )
        return backup

    shutil.rmtree(path)
    print(
        f"Detected broken legacy submodule checkout at {path}; removed because migrate=false "
        f"(missing gitdir: {missing_target})"
    )
    return None


def migrate_legacy_submodules(
    deps: list[dict],
    resolve_dep_path: Callable[[str], Path],
) -> tuple[set[str], list[Path]]:
    force_install_ids: set[str] = set()
    backup_paths: list[Path] = []
    for dep in deps:
        migrate_field = dep.get("migrate")
        if migrate_field is not None and not isinstance(migrate_field, bool):
            raise RuntimeError(f"Dependency '{dep['id']}' has non-boolean migrate flag")
        dep_path = resolve_dep_path(dep["path"])
        if not dep_path.exists():
            continue
        migrate_enabled = bool(migrate_field) if migrate_field is not None else False
        backup_path = migrate_broken_submodule_checkout(dep_path, migrate_enabled)
        if backup_path is not None:
            force_install_ids.add(dep["id"])
            backup_paths.append(backup_path)
    return force_install_ids, backup_paths


def migrate_and_install_legacy_submodules(
    deps: list[dict],
    resolve_dep_path: Callable[[str], Path],
    is_git_repo: Callable[[Path], bool],
    configured_ref: Callable[[dict], tuple[str, str]],
    clone_repo: Callable[[Path, str, str, str], int],
    update_repo: Callable[[Path, str, str, str], int],
) -> int:
    if not has_legacy_submodules(deps, resolve_dep_path):
        return 0

    migrated_ids, backup_paths = migrate_legacy_submodules(deps, resolve_dep_path)
    if not migrated_ids:
        return 0

    dep_map = {dep["id"]: dep for dep in deps}
    for dep_id in migrated_ids:
        dep = dep_map.get(dep_id)
        if dep is None:
            continue
        dep_path = resolve_dep_path(dep["path"])
        ref_type, ref_value = configured_ref(dep)
        if is_git_repo(dep_path):
            rc = update_repo(dep_path, dep["repo"], ref_type, ref_value)
        else:
            rc = clone_repo(dep_path, dep["repo"], ref_type, ref_value)
        if rc != 0:
            return rc

    backup_roots = sorted({str(path.parent) for path in backup_paths})
    if backup_roots:
        print("Legacy dependency backups were saved to:")
        for root in backup_roots:
            print(f"  {root}")
        print("Review these backups and remove them when no longer needed.")

    return 0


def needs_legacy_migration(zde_home: Path) -> bool:
    # Use Zeal-8-bit-OS as the sentinel for old submodule-based layouts.
    sentinel = zde_home / "Zeal-8-bit-OS"
    return broken_submodule_gitdir(sentinel) is not None


def migrate_if_legacy(env: object) -> int:
    zde_home = getattr(env, "zde_home")
    if not isinstance(zde_home, Path):
        raise RuntimeError("Invalid update environment: missing zde_home path")
    if not needs_legacy_migration(zde_home):
        return 0

    # Local import keeps migrate module isolated from update module wiring at import time.
    from mods.update import (
        clone_repo,
        configured_ref,
        is_git_repo,
        load_deps_yaml,
        order_deps_by_dependency,
        resolve_dep_path,
        update_repo,
    )

    deps_file = getattr(env, "deps_file")
    deps = order_deps_by_dependency(load_deps_yaml(deps_file))
    resolver = lambda dep_path: resolve_dep_path(env, dep_path)

    return migrate_and_install_legacy_submodules(
        deps=deps,
        resolve_dep_path=resolver,
        is_git_repo=is_git_repo,
        configured_ref=configured_ref,
        clone_repo=clone_repo,
        update_repo=update_repo,
    )
