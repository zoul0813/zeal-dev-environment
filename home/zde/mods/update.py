from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mods.common import COLLECTION_URL
from mods.process import run as process_run
from mods.process import run_capture as process_run_capture

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


@dataclass
class Env:
    zde_root: Path
    zde_home: Path
    user_path: Path
    deps_file: Path
    lock_file: Path
    collection_file: Path


def run(cmd: list[str], cwd: Path | None = None) -> int:
    return process_run(cmd, cwd=cwd)


def run_capture(cmd: list[str], cwd: Path | None = None) -> str:
    return process_run_capture(cmd, cwd=cwd)


def is_git_repo(path: Path) -> bool:
    if not path.is_dir():
        return False
    return (
        process_run(
            ["git", "-C", str(path), "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        == 0
    )


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
        raw = run_capture(["yq", "-o=json", ".dependencies", str(deps_file)])
        deps = json.loads(raw)

    if not isinstance(deps, list):
        raise RuntimeError("deps.yml must contain a top-level 'dependencies' list")

    ids: set[str] = set()
    alias_owner: dict[str, str] = {}
    for dep in deps:
        if not isinstance(dep, dict):
            raise RuntimeError("Each dependency entry must be a map")
        for key in ("id", "repo", "path"):
            if key not in dep or not isinstance(dep[key], str) or not dep[key].strip():
                raise RuntimeError(f"Dependency missing required string field: {key}")
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
            if tool not in {"cmake", "make"}:
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


def load_lock(lock_file: Path) -> dict[str, Any]:
    if not lock_file.is_file():
        return {"version": 1, "dependencies": {}}

    if yaml is not None:
        with lock_file.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    else:
        if process_run(["yq", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
            raise RuntimeError("PyYAML or yq is required to parse deps-lock.yml")
        raw = run_capture(["yq", "-o=json", ".", str(lock_file)])
        data = json.loads(raw)

    if not isinstance(data, dict):
        raise RuntimeError("deps-lock.yml must be a YAML object")

    deps = data.get("dependencies")
    if not isinstance(deps, dict):
        data["dependencies"] = {}
    return data


def current_commit(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    try:
        return run_capture(["git", "-C", str(path), "rev-parse", "HEAD"])
    except subprocess.CalledProcessError:
        return None


def write_lock(lock_file: Path, lock: dict[str, Any]) -> None:
    if yaml is not None:
        with lock_file.open("w", encoding="utf-8") as f:
            yaml.safe_dump(lock, f, sort_keys=True)
        return

    if process_run(["yq", "--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) != 0:
        raise RuntimeError("PyYAML or yq is required to write deps-lock.yml")

    payload = json.dumps(lock, sort_keys=True)
    rendered = process_run_capture(["yq", "-P", "-o=yaml", ".", "-"], input_text=payload)
    lock_file.write_text(rendered + ("\n" if rendered and not rendered.endswith("\n") else ""), encoding="utf-8")


def configured_ref(dep: dict[str, Any]) -> tuple[str, str]:
    commit = dep.get("commit")
    tag = dep.get("tag")
    branch = dep.get("branch")

    refs = []
    if isinstance(commit, str) and commit.strip():
        refs.append(("commit", commit.strip()))
    if isinstance(tag, str) and tag.strip():
        refs.append(("tag", tag.strip()))
    if isinstance(branch, str) and branch.strip():
        refs.append(("branch", branch.strip()))

    if len(refs) > 1:
        raise RuntimeError(
            f"Dependency '{dep.get('id', dep.get('repo', 'unknown'))}' must declare only one of commit/tag/branch"
        )
    if len(refs) == 1:
        return refs[0]
    return ("branch", "main")


def ensure_origin(path: Path, repo: str) -> int:
    try:
        existing = run_capture(["git", "-C", str(path), "remote", "get-url", "origin"])
    except subprocess.CalledProcessError:
        existing = ""

    if existing == repo:
        return 0

    if existing:
        return run(["git", "-C", str(path), "remote", "set-url", "origin", repo])

    return run(["git", "-C", str(path), "remote", "add", "origin", repo])


def clone_repo(path: Path, repo: str, ref_type: str, ref_value: str) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if ref_type in {"branch", "tag"}:
        return run(["git", "clone", "--depth", "1", "--branch", ref_value, repo, str(path)])

    rc = run(["git", "clone", "--no-checkout", "--depth", "1", repo, str(path)])
    if rc != 0:
        return rc

    rc = run(["git", "-C", str(path), "fetch", "--depth", "1", "origin", ref_value])
    if rc != 0:
        return rc
    return run(["git", "-C", str(path), "checkout", "--detach", "FETCH_HEAD"])


def update_repo(path: Path, repo: str, ref_type: str, ref_value: str) -> int:
    if not (path / ".git").exists():
        return 1

    rc = ensure_origin(path, repo)
    if rc != 0:
        return rc

    if ref_type == "branch":
        rc = run(["git", "-C", str(path), "checkout", ref_value])
        if rc != 0:
            rc = run(["git", "-C", str(path), "checkout", "-B", ref_value, f"origin/{ref_value}"])
            if rc != 0:
                return rc
        return run(["git", "-C", str(path), "pull", "--ff-only", "origin", ref_value])

    if ref_type == "tag":
        rc = run(["git", "-C", str(path), "fetch", "--depth", "1", "origin", "tag", ref_value])
        if rc != 0:
            return rc
        return run(["git", "-C", str(path), "checkout", "--detach", f"tags/{ref_value}"])

    rc = run(["git", "-C", str(path), "fetch", "--depth", "1", "origin", ref_value])
    if rc != 0:
        return rc
    return run(["git", "-C", str(path), "checkout", "--detach", "FETCH_HEAD"])


def resolve_env() -> Env:
    env_zde_path = os.environ.get("ZDE_PATH")
    if env_zde_path:
        zde_root = Path(env_zde_path).resolve()
        deps_file = zde_root / "home" / "zde" / "deps.yml"
        zde_home = zde_root / "home"
    else:
        zde_home = Path("/home/zeal8bit")
        deps_file = zde_home / "zde" / "deps.yml"
        if deps_file.is_file():
            zde_root = Path("/")
        else:
            fallback = Path(__file__).resolve().parents[1]
            deps_file = fallback / "deps.yml"
            zde_home = fallback.parent
            zde_root = fallback.parent.parent

    if not deps_file.is_file():
        raise FileNotFoundError(f"Missing dependency catalog: {deps_file}")

    user_path = Path(os.environ.get("ZDE_USER_PATH", str(Path.home() / ".zeal8bit")))
    lock_file = user_path / "deps-lock.yml"
    collection_file = user_path / "collection.yml"

    return Env(
        zde_root=zde_root,
        zde_home=zde_home,
        user_path=user_path,
        deps_file=deps_file,
        lock_file=lock_file,
        collection_file=collection_file,
    )


def resolve_dep_path(env: Env, dep_path: str) -> Path:
    rel = Path(dep_path)
    if rel.is_absolute():
        return rel

    candidate = env.zde_root / rel
    if candidate.exists():
        return candidate

    if dep_path.startswith("home/"):
        return env.zde_home / dep_path.removeprefix("home/")

    return candidate


def build_lock_entry(
    dep: dict[str, Any],
    ref_type: str,
    ref_value: str,
    status: str,
    updated_at: str,
    current_commit_value: str | None,
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "repo": dep["repo"],
        "path": dep["path"],
        "ref_type": ref_type,
        "ref_value": ref_value,
        "status": status,
        "updated_at": updated_at,
        "current_commit": current_commit_value,
    }
    metadata = dep.get("metadata")
    if isinstance(metadata, dict) and metadata:
        entry["metadata"] = metadata
    depends_on = dep.get("depends_on")
    if isinstance(depends_on, list) and depends_on:
        entry["depends_on"] = depends_on
    return entry


def update_deps(env: Env) -> int:
    # Local import avoids a module-cycle at import time.
    from mods.deps import DepCatalog

    return DepCatalog(env).sync_for_update()


def update_collection(env: Env) -> int:
    env.user_path.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="zde-collection-", dir=env.user_path) as tmp_dir:
        source_file = Path(tmp_dir) / "collection.yml"
        try:
            with urllib.request.urlopen(COLLECTION_URL) as response:
                payload = response.read()
        except urllib.error.URLError as exc:
            print(f"Failed syncing collection catalog: {exc}", file=sys.stderr)
            return 1

        try:
            rendered = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            print(f"Invalid collection catalog encoding: {exc}", file=sys.stderr)
            return 1

        source_file.write_text(rendered, encoding="utf-8")

        try:
            load_deps_yaml(source_file)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f"Invalid collection catalog: {exc}", file=sys.stderr)
            return 1

    if rendered and not rendered.endswith("\n"):
        rendered += "\n"
    env.collection_file.write_text(rendered, encoding="utf-8")
    print(f"Collection catalog updated: {env.collection_file}")
    return 0


def run_update(env: Env) -> int:
    rc = update_deps(env)
    if rc != 0:
        return rc
    return update_collection(env)


def main() -> int:
    env = resolve_env()
    return run_update(env)


if __name__ == "__main__":
    raise SystemExit(main())
