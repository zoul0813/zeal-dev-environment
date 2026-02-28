from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from mods.process import run as process_run
from mods.process import run_capture as process_run_capture

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


def _declared_categories(dep: dict[str, Any]) -> list[str]:
    metadata = dep.get("metadata")
    if not isinstance(metadata, dict):
        return []
    category = metadata.get("category")
    if isinstance(category, str):
        return [category]
    if isinstance(category, list):
        return [item for item in category if isinstance(item, str)]
    return []


def _repo_name_from_id(dep_id: str) -> str:
    if "/" in dep_id:
        return dep_id.split("/", 1)[1]
    return dep_id


def _default_dep_path(dep: dict[str, Any]) -> str:
    dep_id = str(dep["id"])
    categories = _declared_categories(dep)
    is_core = any(category.casefold() == "core" for category in categories)
    if is_core:
        return f"home/{_repo_name_from_id(dep_id)}"
    return f"extras/{dep_id}"


def _validate_dep_env(dep: dict[str, Any]) -> None:
    env_items = dep.get("env")
    if env_items is None:
        return
    if not isinstance(env_items, list):
        raise RuntimeError(f"Dependency '{dep['id']}' has invalid env list")

    for item in env_items:
        if isinstance(item, str):
            if not item.strip():
                raise RuntimeError(f"Dependency '{dep['id']}' has invalid env entry")
            continue
        if not isinstance(item, dict):
            raise RuntimeError(f"Dependency '{dep['id']}' has invalid env entry")

        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            raise RuntimeError(f"Dependency '{dep['id']}' has invalid env.name")

        env_path = item.get("path")
        if env_path is not None and (not isinstance(env_path, str) or not env_path.strip()):
            raise RuntimeError(f"Dependency '{dep['id']}' has invalid env.path")


def load_deps_yaml(deps_file: Path) -> list[dict[str, Any]]:
    if not deps_file.is_file():
        raise FileNotFoundError(f"Missing dependency catalog: {deps_file}")

    deps: Any = None
    if yaml is not None:
        with deps_file.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        deps = doc.get("dependencies")
    else:
        if process_run(["yq", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            raise RuntimeError("PyYAML or yq is required to parse deps.yml")
        raw = process_run_capture(["yq", "-o=json", ".dependencies", str(deps_file)])
        deps = json.loads(raw)

    if not isinstance(deps, list):
        raise RuntimeError("deps.yml must contain a top-level 'dependencies' list")

    ids: set[str] = set()
    alias_owner: dict[str, str] = {}
    for dep in deps:
        if not isinstance(dep, dict):
            raise RuntimeError("Each dependency entry must be a map")
        for key in ("id", "repo"):
            if key not in dep or not isinstance(dep[key], str) or not dep[key].strip():
                raise RuntimeError(f"Dependency missing required string field: {key}")
        raw_path = dep.get("path")
        if raw_path is None:
            dep["path"] = _default_dep_path(dep)
        elif not isinstance(raw_path, str) or not raw_path.strip():
            raise RuntimeError(f"Dependency missing required string field: path")
        required = dep.get("required")
        if required is not None and not isinstance(required, bool):
            raise RuntimeError(f"Dependency '{dep['id']}' has non-boolean required flag")
        metadata = dep.get("metadata")
        if metadata is None:
            metadata = {}
            dep["metadata"] = metadata
        elif not isinstance(metadata, dict):
            raise RuntimeError(f"Dependency '{dep['id']}' has non-map metadata")

        category = metadata.get("category")
        if category is None:
            metadata["category"] = ["Other"]
        elif isinstance(category, str):
            if not category.strip():
                raise RuntimeError(f"Dependency '{dep['id']}' has invalid metadata.category")
            metadata["category"] = [category]
        elif isinstance(category, list):
            if any(not isinstance(item, str) or not item.strip() for item in category):
                raise RuntimeError(f"Dependency '{dep['id']}' has invalid metadata.category list")
        else:
            raise RuntimeError(f"Dependency '{dep['id']}' has invalid metadata.category")

        aliases = dep.get("aliases")
        if aliases is not None:
            if not isinstance(aliases, list) or any(not isinstance(item, str) or not item.strip() for item in aliases):
                raise RuntimeError(f"Dependency '{dep['id']}' has invalid aliases list")
        depends_on = dep.get("depends_on")
        if depends_on is not None:
            if not isinstance(depends_on, list) or any(not isinstance(item, str) or not item.strip() for item in depends_on):
                raise RuntimeError(f"Dependency '{dep['id']}' has invalid depends_on list")
        build = dep.get("build")
        if build is not None:
            if not isinstance(build, dict):
                raise RuntimeError(f"Dependency '{dep['id']}' has invalid build config")
            tool = build.get("tool")
            commands = build.get("commands")
            if commands is not None:
                if (
                    not isinstance(commands, list)
                    or not commands
                    or any(not isinstance(item, str) or not item.strip() for item in commands)
                ):
                    raise RuntimeError(f"Dependency '{dep['id']}' has invalid build.commands list")
            if commands is None and tool not in {"cmake", "make"}:
                raise RuntimeError(
                    f"Dependency '{dep['id']}' build config must define build.commands or build.tool (cmake/make)"
                )
            if tool is not None and tool not in {"cmake", "make"}:
                raise RuntimeError(f"Dependency '{dep['id']}' build.tool must be one of: cmake, make")
            build_args = build.get("args")
            if build_args is not None:
                if not isinstance(build_args, list) or any(not isinstance(item, str) for item in build_args):
                    raise RuntimeError(f"Dependency '{dep['id']}' has invalid build.args list")
            artifacts = build.get("artifacts")
            if artifacts is not None:
                if not isinstance(artifacts, list) or any(not isinstance(item, str) or not item.strip() for item in artifacts):
                    raise RuntimeError(f"Dependency '{dep['id']}' has invalid build.artifacts list")
            build_root = build.get("root")
            if build_root is not None:
                if not isinstance(build_root, str) or not build_root.strip():
                    raise RuntimeError(f"Dependency '{dep['id']}' has invalid build.root")
        _validate_dep_env(dep)
        dep_id = dep["id"]
        if dep_id in ids:
            raise RuntimeError(f"Duplicate dependency id in deps.yml: {dep_id}")
        ids.add(dep_id)

    for dep in deps:
        dep_id = dep["id"]
        dep_id_fold = dep_id.casefold()
        if dep_id_fold in alias_owner and alias_owner[dep_id_fold] != dep_id:
            raise RuntimeError(f"Dependency id '{dep_id}' conflicts with alias '{dep_id}' on '{alias_owner[dep_id_fold]}'")
        alias_owner[dep_id_fold] = dep_id
        for alias in dep.get("aliases", []):
            alias_fold = alias.casefold()
            owner = alias_owner.get(alias_fold)
            if owner is not None and owner != dep_id:
                raise RuntimeError(f"Alias '{alias}' on '{dep_id}' conflicts with '{owner}'")
            alias_owner[alias_fold] = dep_id

    for dep in deps:
        dep_id = dep["id"]
        for parent in dep.get("depends_on", []):
            if parent not in ids:
                raise RuntimeError(f"Dependency '{dep_id}' depends on unknown id '{parent}'")
            if parent == dep_id:
                raise RuntimeError(f"Dependency '{dep_id}' cannot depend on itself")
    return deps


def merge_deps_lists(primary: list[dict[str, Any]], secondary: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = list(primary)
    by_id: dict[str, dict[str, Any]] = {dep["id"]: dep for dep in merged}

    for dep in secondary:
        existing = by_id.get(dep["id"])
        if existing is None:
            merged.append(dep)
            by_id[dep["id"]] = dep
            continue

        existing_meta = existing.get("metadata")
        dep_meta = dep.get("metadata")
        if isinstance(existing_meta, dict) and isinstance(dep_meta, dict):
            existing_categories = existing_meta.get("category", [])
            dep_categories = dep_meta.get("category", [])
            if isinstance(existing_categories, list) and isinstance(dep_categories, list):
                seen_categories = {str(item).casefold() for item in existing_categories}
                for category in dep_categories:
                    key = category.casefold()
                    if key in seen_categories:
                        continue
                    existing_categories.append(category)
                    seen_categories.add(key)

            for key, value in dep_meta.items():
                if key not in existing_meta:
                    existing_meta[key] = value

        existing_aliases = existing.get("aliases")
        dep_aliases = dep.get("aliases")
        if existing_aliases is None and isinstance(dep_aliases, list):
            existing["aliases"] = list(dep_aliases)
            continue
        if isinstance(existing_aliases, list) and isinstance(dep_aliases, list):
            seen_aliases = {str(item).casefold() for item in existing_aliases}
            for alias in dep_aliases:
                key = alias.casefold()
                if key in seen_aliases:
                    continue
                existing_aliases.append(alias)
                seen_aliases.add(key)

    return merged


def order_deps_by_dependency(deps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dep_map = {dep["id"]: dep for dep in deps}
    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[dict[str, Any]] = []

    def visit(dep_id: str) -> None:
        if dep_id in visited:
            return
        if dep_id in visiting:
            raise RuntimeError(f"Dependency cycle detected at '{dep_id}'")
        visiting.add(dep_id)
        dep = dep_map[dep_id]
        for parent in dep.get("depends_on", []):
            visit(parent)
        visiting.remove(dep_id)
        visited.add(dep_id)
        ordered.append(dep)

    for dep in deps:
        visit(dep["id"])

    return ordered
