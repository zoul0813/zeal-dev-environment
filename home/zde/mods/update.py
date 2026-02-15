from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


@dataclass
class Env:
    zde_root: Path
    zde_home: Path
    deps_file: Path
    lock_file: Path


def run(cmd: list[str], cwd: Path | None = None) -> int:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False).returncode


def run_capture(cmd: list[str], cwd: Path | None = None) -> str:
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def load_deps_yaml(deps_file: Path) -> list[dict[str, Any]]:
    if not deps_file.is_file():
        raise FileNotFoundError(f"Missing dependency catalog: {deps_file}")

    deps: Any = None
    if yaml is not None:
        with deps_file.open("r", encoding="utf-8") as f:
            doc = yaml.safe_load(f) or {}
        deps = doc.get("dependencies")
    else:
        yq_check = subprocess.run(
            ["yq", "--version"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if yq_check.returncode != 0:
            raise RuntimeError("PyYAML or yq is required to parse deps.yml")
        raw = run_capture(["yq", "-o=json", ".dependencies", str(deps_file)])
        deps = json.loads(raw)

    if not isinstance(deps, list):
        raise RuntimeError("deps.yml must contain a top-level 'dependencies' list")

    ids: set[str] = set()
    for dep in deps:
        if not isinstance(dep, dict):
            raise RuntimeError("Each dependency entry must be a map")
        for key in ("id", "repo", "path"):
            if key not in dep or not isinstance(dep[key], str) or not dep[key].strip():
                raise RuntimeError(f"Dependency missing required string field: {key}")
        dep_id = dep["id"]
        if dep_id in ids:
            raise RuntimeError(f"Duplicate dependency id in deps.yml: {dep_id}")
        ids.add(dep_id)
    return deps


def load_lock(lock_file: Path) -> dict[str, Any]:
    if not lock_file.is_file():
        return {"version": 1, "dependencies": {}}

    with lock_file.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise RuntimeError("deps.lock must be a JSON object")

    deps = data.get("dependencies")
    if not isinstance(deps, dict):
        data["dependencies"] = {}
    return data


def migrate_lock_by_repo(
    lock_deps: dict[str, Any],
    deps: list[dict[str, Any]],
) -> dict[str, Any]:
    by_repo: dict[str, Any] = {}
    for dep in deps:
        repo = dep["repo"]
        dep_id = dep["id"]

        candidate = lock_deps.get(repo)
        if not isinstance(candidate, dict):
            candidate = lock_deps.get(dep_id)
        if not isinstance(candidate, dict):
            candidate = {}

        by_repo[repo] = candidate
    return by_repo


def current_commit(path: Path) -> str | None:
    if not (path / ".git").exists():
        return None
    try:
        return run_capture(["git", "-C", str(path), "rev-parse", "HEAD"])
    except subprocess.CalledProcessError:
        return None


def update_repo(path: Path, branch: str) -> int:
    if not (path / ".git").exists():
        return 0

    rc = run(["git", "-C", str(path), "fetch", "origin", branch])
    if rc != 0:
        return rc

    try:
        current_branch = run_capture(["git", "-C", str(path), "rev-parse", "--abbrev-ref", "HEAD"])
    except subprocess.CalledProcessError:
        current_branch = "HEAD"

    if current_branch != branch:
        rc = run(["git", "-C", str(path), "checkout", branch])
        if rc != 0:
            rc = run(["git", "-C", str(path), "checkout", "-B", branch, f"origin/{branch}"])
            if rc != 0:
                return rc

    rc = run(["git", "-C", str(path), "pull", "--ff-only", "origin", branch])
    return rc


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

    user_path = Path(os.environ.get("ZDE_USER_PATH", str(zde_home / ".zeal8bit")))
    lock_file = user_path / "deps.lock"

    return Env(
        zde_root=zde_root,
        zde_home=zde_home,
        deps_file=deps_file,
        lock_file=lock_file,
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


def update_deps(env: Env) -> int:
    env.lock_file.parent.mkdir(parents=True, exist_ok=True)

    deps = load_deps_yaml(env.deps_file)
    lock = load_lock(env.lock_file)
    lock_deps_raw: dict[str, Any] = lock.setdefault("dependencies", {})
    lock_deps: dict[str, Any] = migrate_lock_by_repo(lock_deps_raw, deps)
    lock["dependencies"] = lock_deps

    now = datetime.now(timezone.utc).isoformat()

    active_repos = set()
    for dep in deps:
        repo = dep["repo"]
        dep_id = dep["id"]
        active_repos.add(repo)
        dep_path = resolve_dep_path(env, dep["path"])
        installed = dep_path.is_dir() and (dep_path / ".git").exists()

        entry = lock_deps.get(repo, {})
        if not isinstance(entry, dict):
            entry = {}

        entry["key"] = repo
        entry["id"] = dep_id
        entry["repo"] = repo
        entry["path"] = dep["path"]
        entry["branch"] = dep.get("branch", "main")
        entry["installed"] = installed
        entry["metadata"] = {k: v for k, v in dep.items() if k not in {"id", "repo", "path", "branch"}}

        lock_deps[repo] = entry

    for repo in list(lock_deps.keys()):
        if repo not in active_repos:
            del lock_deps[repo]

    for dep in deps:
        repo = dep["repo"]
        dep_id = dep["id"]
        entry = lock_deps[repo]
        if not entry.get("installed"):
            entry["status"] = "not_installed"
            entry["updated_at"] = now
            entry["current_commit"] = None
            continue

        dep_path = env.zde_path / entry["path"]
        branch = str(entry.get("branch") or "main")
        dep_path = resolve_dep_path(env, entry["path"])

        rc = update_repo(dep_path, branch)
        if rc != 0:
            entry["status"] = "update_failed"
            entry["updated_at"] = now
            lock["updated_at"] = now
            with env.lock_file.open("w", encoding="utf-8") as f:
                json.dump(lock, f, indent=2, sort_keys=True)
                f.write("\n")
            print(f"Failed updating dependency: {dep_id}", file=sys.stderr)
            return rc

        entry["status"] = "updated"
        entry["updated_at"] = now
        entry["current_commit"] = current_commit(dep_path)

    lock["updated_at"] = now
    with env.lock_file.open("w", encoding="utf-8") as f:
        json.dump(lock, f, indent=2, sort_keys=True)
        f.write("\n")

    print(f"Dependency lock updated: {env.lock_file}")
    return 0


def main() -> int:
    env = resolve_env()
    return update_deps(env)


if __name__ == "__main__":
    raise SystemExit(main())
