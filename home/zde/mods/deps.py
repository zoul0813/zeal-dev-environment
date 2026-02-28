from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from mods.migrate import migrate_broken_submodule_checkout
from mods.catalog import load_deps_yaml, merge_deps_lists, order_deps_by_dependency
from mods.config import Config
from mods.update import (
    build_lock_entry,
    update_repo,
    clone_repo,
    configured_ref,
    current_commit,
    is_git_repo,
    load_lock,
    resolve_dep_path,
    resolve_env,
    write_lock,
)


def _wrap_config_value(value: Any) -> Any:
    if isinstance(value, dict):
        return DepConfig(value)
    if isinstance(value, list):
        return [_wrap_config_value(item) for item in value]
    return value


def get_skip_sync_installed_config() -> bool:
    cfg = Config.load()
    value = cfg.get("deps.skip-sync-installed")
    return bool(value)


def set_skip_sync_installed_config(enabled: bool) -> None:
    cfg = Config.load()
    cfg.set("deps.skip-sync-installed", bool(enabled))
    cfg.save()


@dataclass(frozen=True)
class DepConfig:
    _data: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        if name in self._data:
            return _wrap_config_value(self._data[name])
        raise AttributeError(name)

    def __getitem__(self, key: str) -> Any:
        return _wrap_config_value(self._data[key])

    def get(self, key: str, default: Any = None) -> Any:
        if key not in self._data:
            return default
        return _wrap_config_value(self._data[key])


@dataclass
class Dep:
    catalog: "DepCatalog"
    raw: dict[str, Any]

    def __getattr__(self, name: str) -> Any:
        if name in self.raw:
            return _wrap_config_value(self.raw[name])
        raise AttributeError(name)

    @property
    def path_resolved(self) -> Path:
        return resolve_dep_path(self.catalog.env, self.path, self.raw)

    @property
    def required(self) -> bool:
        return bool(self.raw.get("required", False))

    @property
    def tracked(self) -> bool:
        return self.id in self.catalog.lock_deps

    @property
    def installed(self) -> bool:
        return bool(self.catalog.installed_by_id.get(self.id, False))

    @property
    def aliases(self) -> list[str]:
        aliases = self.raw.get("aliases", [])
        if not isinstance(aliases, list):
            return []
        return [alias for alias in aliases if isinstance(alias, str)]

    @property
    def depends_on(self) -> list[str]:
        parents = self.raw.get("depends_on", [])
        if not isinstance(parents, list):
            return []
        return [parent for parent in parents if isinstance(parent, str)]

    @property
    def categories(self) -> list[str]:
        metadata = self.raw.get("metadata", {})
        if not isinstance(metadata, dict):
            values = ["Other"]
        else:
            categories = metadata.get("category", ["Other"])
            if not isinstance(categories, list):
                values = ["Other"]
            else:
                values = [category for category in categories if isinstance(category, str) and category.strip()]
                if not values:
                    values = ["Other"]
        if self.installed and not any(category.casefold() == "installed" for category in values):
            values = [*values, "installed"]
        return values

    @property
    def preferred_label(self) -> str:
        aliases = self.aliases
        if aliases:
            first = aliases[0].strip()
            if first:
                return first
        return self.id

    @property
    def missing_dependency_ids(self) -> list[str]:
        return [parent for parent in self.depends_on if not self.catalog.installed_by_id.get(parent, False)]

    @property
    def state(self) -> str:
        if self.required and not self.installed:
            return "required-miss"
        missing = self.missing_dependency_ids
        if self.installed and missing:
            labels = [self.catalog.by_id[parent].preferred_label for parent in missing if parent in self.catalog.by_id]
            if labels:
                return f"broken({','.join(labels)})"
            return "broken-deps"
        if self.installed and not self.tracked:
            return "untracked"
        if self.installed:
            return "ok"
        return "-"

    @property
    def has_error(self) -> bool:
        return self.state.startswith("broken") or self.state == "required-miss"

    @property
    def marker(self) -> str:
        if self.has_error:
            return "[?]"
        if self.installed:
            return "[x]"
        return "[ ]"

    @property
    def display_name(self) -> str:
        metadata = self.raw.get("metadata", {})
        if not isinstance(metadata, dict):
            return self.id
        raw_name = metadata.get("name")
        if not isinstance(raw_name, str) or not raw_name.strip():
            return self.id
        return f"{raw_name.strip()} ({self.id})"

    def artifact_paths(self) -> list[tuple[Path, Path]]:
        build = self.raw.get("build")
        if not isinstance(build, dict):
            return []
        artifacts = build.get("artifacts")
        if not isinstance(artifacts, list):
            return []

        paths: list[tuple[Path, Path]] = []
        for raw in artifacts:
            if not isinstance(raw, str) or not raw.strip():
                continue
            raw_text = raw.strip()
            copy_contents = raw_text.endswith(("/", "\\"))
            normalized = raw_text.rstrip("/\\")
            if not normalized:
                continue
            p = Path(normalized)
            source = p if p.is_absolute() else self.path_resolved / p
            if p.is_absolute():
                rel_hint = Path(".") if copy_contents else Path(source.name)
            else:
                rel_hint = p.parent if copy_contents else p
            paths.append((source, rel_hint))
        return paths

    def install(self) -> int:
        return self.catalog.install_dep(self.id)

    def remove(self) -> int:
        return self.catalog.remove_dep(self.id)

    def build(self) -> int:
        return self.catalog.build_dep(self.id)

    def update(self) -> int:
        return self.catalog.update_dep(self.id)

    def stage(self, target: str) -> int:
        # Local import keeps deps module independent from image command module at import time.
        from cmds import image as image_cmd

        target_id = target.strip().lower()
        targets = set(image_cmd.available_stage_targets())
        if target_id not in targets:
            supported = ", ".join(sorted(targets))
            print(f"Target must be one of: {supported}")
            return 1

        artifact_paths = self.artifact_paths()
        if not artifact_paths:
            print(f"No build.artifacts configured for {self.id}")
            return 1

        build_cfg = self.raw.get("build")
        stage_root = build_cfg.get("root") if isinstance(build_cfg, dict) else None
        image_cmd.stage_artifacts_to_target(artifact_paths, target_id, stage_root=stage_root)

        missing = 0
        for source, _ in artifact_paths:
            if not source.exists():
                missing += 1
        if missing > 0:
            print(f"Staging had missing artifacts for {self.id}")
            return 1

        target_label = "romdisk" if target_id == "romdisk" else f"image {target_id}"
        print(f"Staged artifacts for {self.id} -> {target_label}")
        return 0

    def render_info(self) -> str:
        lines: list[str] = []

        def _pretty_label(key: str) -> str:
            return key.replace("_", " ").title()

        def _append_value(value: Any, indent: str = "  ") -> None:
            if isinstance(value, list):
                if not value:
                    lines.append(f"{indent}-")
                    return
                for item in value:
                    if isinstance(item, (list, dict)):
                        lines.append(f"{indent}-")
                        _append_value(item, indent + "  ")
                    else:
                        lines.append(f"{indent}- {item}")
                return
            if isinstance(value, dict):
                if not value:
                    lines.append(f"{indent}-")
                    return
                for k in sorted(value.keys()):
                    v = value[k]
                    if isinstance(v, (list, dict)):
                        lines.append(f"{indent}{_pretty_label(str(k))}:")
                        _append_value(v, indent + "  ")
                    else:
                        lines.append(f"{indent}{_pretty_label(str(k))}: {v}")
                return
            lines.append(f"{indent}{value}")

        lines.append(f"Id: {self.id}")
        lines.append(f"Installed: {'yes' if self.installed else 'no'}")
        lines.append(f"Tracked: {'yes' if self.tracked else 'no'}")
        lines.append(f"State: {self.state}")
        for key in sorted(self.raw.keys()):
            if key == "id":
                continue
            label = _pretty_label(key)
            value = self.raw[key]
            if isinstance(value, (dict, list)):
                lines.append(f"{label}:")
                _append_value(value)
                continue
            lines.append(f"{label}: {value}")

        return "\n".join(lines)


class DepCatalog:
    def __init__(self, env: object | None = None) -> None:
        self.env = resolve_env() if env is None else env
        deps_raw = load_deps_yaml(self.env.deps_file)
        if self.env.collection_file.is_file():
            collection_raw = load_deps_yaml(self.env.collection_file)
            deps_raw = merge_deps_lists(deps_raw, collection_raw)
        self._deps_raw = order_deps_by_dependency(deps_raw)
        self.by_id: dict[str, Dep] = {dep["id"]: Dep(self, dep) for dep in self._deps_raw}
        self.lock: dict[str, Any] = {}
        self.lock_deps: dict[str, Any] = {}
        self.installed_by_id: dict[str, bool] = {}
        self.refresh()

    @property
    def deps(self) -> list[Dep]:
        return [self.by_id[dep_id] for dep_id in sorted(self.by_id.keys())]

    @property
    def categories(self) -> list[str]:
        found: dict[str, str] = {}
        for dep in self.deps:
            for category in dep.categories:
                key = category.casefold()
                if key not in found:
                    found[key] = category
        ordered_keys = sorted(key for key in found.keys() if key != "installed")
        if "installed" in found:
            ordered_keys.insert(0, "installed")
        return [found[key] for key in ordered_keys]

    def installed(self) -> list[Dep]:
        return [dep for dep in self.deps if dep.installed]

    def category(self, raw_category: str) -> list[Dep]:
        wanted = raw_category.strip().casefold()
        if not wanted:
            return self.deps
        return [dep for dep in self.deps if any(category.casefold() == wanted for category in dep.categories)]

    def refresh(self) -> None:
        self.lock = load_lock(self.env.lock_file)
        lock_deps = self.lock.get("dependencies", {})
        self.lock_deps = lock_deps if isinstance(lock_deps, dict) else {}
        self.installed_by_id = {}
        for dep_id, dep in self.by_id.items():
            self.installed_by_id[dep_id] = is_git_repo(dep.path_resolved)

    def get(self, dep_id: str) -> Dep | None:
        return self.by_id.get(dep_id)

    def resolve(self, raw_id: str) -> Dep | None:
        if raw_id in self.by_id:
            return self.by_id[raw_id]

        wanted = raw_id.casefold()
        matches: dict[str, Dep] = {}
        for dep in self.by_id.values():
            if dep.id.casefold() == wanted:
                matches[dep.id] = dep
            for alias in dep.aliases:
                if alias.casefold() == wanted:
                    matches[dep.id] = dep
            if self._repo_name_from_id(dep.id).casefold() == wanted:
                matches[dep.id] = dep

        if len(matches) == 0:
            return None
        if len(matches) > 1:
            choices = ", ".join(sorted(matches.keys()))
            raise RuntimeError(f"Ambiguous dependency identifier '{raw_id}'. Matches: {choices}")
        return next(iter(matches.values()))

    def dependency_chain(self, dep_id: str) -> list[str]:
        visiting: set[str] = set()
        visited: set[str] = set()
        ordered: list[str] = []

        def visit(cur: str) -> None:
            if cur in visited:
                return
            if cur in visiting:
                raise RuntimeError(f"Dependency cycle detected at '{cur}'")
            dep = self.by_id.get(cur)
            if dep is None:
                raise RuntimeError(f"Unknown dependency id in chain: {cur}")
            visiting.add(cur)
            for parent in dep.depends_on:
                visit(parent)
            visiting.remove(cur)
            visited.add(cur)
            ordered.append(cur)

        visit(dep_id)
        return ordered

    def install_dep(
        self,
        dep_id: str,
        *,
        allow_required: bool = False,
        include_dependencies: bool = True,
    ) -> int:
        dep = self.by_id[dep_id]
        if dep.required and not allow_required:
            print(f"Dependency is required and managed by update: {dep_id}")
            return 1

        install_ids = self.dependency_chain(dep_id) if include_dependencies else [dep_id]
        for install_id in install_ids:
            install_dep = self.by_id[install_id]
            dep_path = install_dep.path_resolved
            has_git = is_git_repo(dep_path)
            if not has_git and dep_path.exists():
                migrated = migrate_broken_submodule_checkout(dep_path, True)
                if migrated:
                    has_git = False

            ref_type, ref_value = configured_ref(install_dep.raw)

            if dep_path.exists() and not has_git:
                try:
                    has_entries = next(dep_path.iterdir(), None) is not None
                except OSError:
                    has_entries = True
                if has_entries:
                    print(f"Dependency path exists but is not a git repo: {dep_path}")
                    return 1

            if has_git:
                self._write_dep_lock_entry(install_dep, "synced")
                print(f"Dependency already installed: {install_id}")
                continue

            rc = clone_repo(dep_path, install_dep.repo, ref_type, ref_value)
            if rc != 0:
                print(f"Failed installing dependency: {install_id}")
                return rc

            rc = self._run_build_for_dep(install_dep)
            if rc != 0:
                self._write_dep_lock_entry(install_dep, "build_failed")
                print(f"Failed building dependency: {install_id}")
                return rc

            self._write_dep_lock_entry(install_dep, "synced")
            print(f"Installed dependency: {install_id}")

        self.refresh()
        return 0

    def remove_dep(self, dep_id: str) -> int:
        dep = self.by_id[dep_id]
        if dep.required:
            print(f"Cannot remove required dependency: {dep_id}")
            return 1

        dep_path = dep.path_resolved
        if dep_path.exists():
            if dep_path.is_dir():
                shutil.rmtree(dep_path)
            else:
                dep_path.unlink()

        self._remove_dep_lock_entry(dep_id)
        print(f"Removed dependency: {dep_id}")
        self.refresh()
        return 0

    def build_dep(self, dep_id: str) -> int:
        from mods.requirements import require_deps

        dep = self.by_id[dep_id]
        needed_ids = [dep.id, *dep.depends_on]
        if not require_deps(needed_ids):
            return 1

        dep_path = dep.path_resolved
        if not is_git_repo(dep_path):
            print(f"Dependency not installed: {dep_id}")
            return 1

        build_cfg = dep.raw.get("build")
        if not isinstance(build_cfg, dict):
            print(f"No build configured for dependency: {dep_id}")
            self._write_dep_lock_entry(dep, "synced")
            self.refresh()
            return 0

        rc = self._run_build_for_dep(dep)
        if rc != 0:
            self._write_dep_lock_entry(dep, "build_failed")
            print(f"Failed building dependency: {dep_id}")
            self.refresh()
            return rc

        self._write_dep_lock_entry(dep, "synced")
        print(f"Built dependency: {dep_id}")
        self.refresh()
        return 0

    def update_dep(self, dep_id: str, *, include_dependencies: bool = True) -> int:
        update_ids = self.dependency_chain(dep_id) if include_dependencies else [dep_id]

        for update_id in update_ids:
            dep = self.by_id[update_id]
            dep_path = dep.path_resolved
            has_git = is_git_repo(dep_path)
            if not has_git and dep_path.exists():
                migrated = migrate_broken_submodule_checkout(dep_path, True)
                if migrated:
                    has_git = False

            ref_type, ref_value = configured_ref(dep.raw)

            if dep_path.exists() and not has_git:
                try:
                    has_entries = next(dep_path.iterdir(), None) is not None
                except OSError:
                    has_entries = True
                if has_entries:
                    print(f"Dependency path exists but is not a git repo: {dep_path}")
                    return 1

            newly_installed = not has_git
            if newly_installed:
                rc = clone_repo(dep_path, dep.repo, ref_type, ref_value)
            else:
                rc = update_repo(dep_path, dep.repo, ref_type, ref_value)

            if rc != 0:
                self._write_dep_lock_entry(dep, "sync_failed")
                print(f"Failed updating dependency: {update_id}")
                return rc

            if newly_installed:
                rc = self._run_build_for_dep(dep)
                if rc != 0:
                    self._write_dep_lock_entry(dep, "build_failed")
                    print(f"Failed building dependency: {update_id}")
                    return rc

            self._write_dep_lock_entry(dep, "synced")
            if newly_installed:
                print(f"Installed dependency: {update_id}")
            else:
                print(f"Updated dependency: {update_id}")

        self.refresh()
        return 0

    def sync_for_update(self) -> int:
        self.env.lock_file.parent.mkdir(parents=True, exist_ok=True)

        lock = load_lock(self.env.lock_file)
        lock.setdefault("dependencies", {})
        lock_deps: dict[str, Any] = {}
        lock["dependencies"] = lock_deps

        skip_installed_sync = self._skip_sync_for_installed()
        announced_skip_mode = False
        now = datetime.now(timezone.utc).isoformat()
        for dep in self.deps:
            ref_type, ref_value = configured_ref(dep.raw)
            dep_path = dep.path_resolved
            has_git = is_git_repo(dep_path)

            if not has_git and not dep.required:
                continue

            if dep_path.exists() and not has_git:
                try:
                    has_entries = next(dep_path.iterdir(), None) is not None
                except OSError:
                    has_entries = True
                if has_entries:
                    if not dep.required:
                        continue
                    lock["updated_at"] = now
                    write_lock(self.env.lock_file, lock)
                    print(
                        f"Dependency path exists but is not a git repo: {dep.id} ({dep_path})",
                        file=sys.stderr,
                    )
                    return 1

            if has_git and skip_installed_sync:
                if not announced_skip_mode:
                    print("Local dep mode enabled: skipping git sync for already-installed dependencies.")
                    announced_skip_mode = True
                lock_deps[dep.id] = build_lock_entry(
                    dep=dep.raw,
                    ref_type=ref_type,
                    ref_value=ref_value,
                    status="local",
                    updated_at=now,
                    current_commit_value=current_commit(dep_path),
                )
                continue

            newly_installed = not has_git
            if newly_installed:
                rc = clone_repo(dep_path, dep.repo, ref_type, ref_value)
            else:
                rc = update_repo(dep_path, dep.repo, ref_type, ref_value)

            if rc != 0:
                if has_git:
                    lock_deps[dep.id] = build_lock_entry(
                        dep=dep.raw,
                        ref_type=ref_type,
                        ref_value=ref_value,
                        status="sync_failed",
                        updated_at=now,
                        current_commit_value=current_commit(dep_path),
                    )
                lock["updated_at"] = now
                write_lock(self.env.lock_file, lock)
                print(f"Failed syncing dependency: {dep.id}", file=sys.stderr)
                return rc

            if newly_installed:
                rc = self._run_build_for_dep(dep)
                if rc != 0:
                    lock_deps[dep.id] = build_lock_entry(
                        dep=dep.raw,
                        ref_type=ref_type,
                        ref_value=ref_value,
                        status="build_failed",
                        updated_at=now,
                        current_commit_value=current_commit(dep_path),
                    )
                    lock["updated_at"] = now
                    write_lock(self.env.lock_file, lock)
                    print(f"Failed building dependency: {dep.id}", file=sys.stderr)
                    return rc

            lock_deps[dep.id] = build_lock_entry(
                dep=dep.raw,
                ref_type=ref_type,
                ref_value=ref_value,
                status="synced",
                updated_at=now,
                current_commit_value=current_commit(dep_path),
            )

        lock["updated_at"] = now
        write_lock(self.env.lock_file, lock)
        self.refresh()
        print(f"Dependency lock updated: {self.env.lock_file}")
        return 0

    def _skip_sync_for_installed(self) -> bool:
        return get_skip_sync_installed_config()

    def _run_build_for_dep(self, dep: Dep) -> int:
        build = dep.raw.get("build")
        if not isinstance(build, dict):
            return 0

        tool = build.get("tool")
        args = build.get("args", [])
        if not isinstance(args, list):
            print(f"Invalid build.args for dependency: {dep.id}")
            return 1
        if tool not in {"cmake", "make"}:
            print(f"Invalid build.tool for dependency: {dep.id}")
            return 1
        for arg in args:
            if not isinstance(arg, str):
                print(f"Invalid non-string build arg for dependency: {dep.id}")
                return 1

        print(f"Building dependency: {dep.id} ({tool})")
        old_cwd = Path.cwd()
        try:
            os.chdir(dep.path_resolved)
            if tool == "cmake":
                from cmds import cmake as cmd_cmake

                return int(cmd_cmake.main(args))

            from cmds import make as cmd_make

            return int(cmd_make.main(args))
        finally:
            os.chdir(old_cwd)

    def _write_dep_lock_entry(self, dep: Dep, status: str) -> None:
        lock = load_lock(self.env.lock_file)
        lock_deps = lock.setdefault("dependencies", {})
        if not isinstance(lock_deps, dict):
            lock_deps = {}
            lock["dependencies"] = lock_deps
        now = datetime.now(timezone.utc).isoformat()
        ref_type, ref_value = configured_ref(dep.raw)
        lock_deps[dep.id] = build_lock_entry(
            dep=dep.raw,
            ref_type=ref_type,
            ref_value=ref_value,
            status=status,
            updated_at=now,
            current_commit_value=current_commit(dep.path_resolved),
        )
        lock["updated_at"] = now
        write_lock(self.env.lock_file, lock)

    def _remove_dep_lock_entry(self, dep_id: str) -> None:
        lock = load_lock(self.env.lock_file)
        lock_deps = lock.setdefault("dependencies", {})
        if dep_id in lock_deps:
            del lock_deps[dep_id]
        lock["updated_at"] = datetime.now(timezone.utc).isoformat()
        write_lock(self.env.lock_file, lock)

    @staticmethod
    def _repo_name_from_id(dep_id: str) -> str:
        if "/" in dep_id:
            return dep_id.split("/", 1)[1]
        return dep_id


def load_catalog() -> DepCatalog:
    return DepCatalog()


def load_deps() -> list[Dep]:
    return load_catalog().deps
