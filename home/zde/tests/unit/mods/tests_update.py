from __future__ import annotations

import builtins
import json
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from mods.update import (
    Env,
    _is_git_tracked_file,
    build_lock_entry,
    clone_repo,
    configured_ref,
    current_commit,
    ensure_origin,
    is_git_repo,
    load_lock,
    resolve_dep_path,
    resolve_env,
    run,
    run_capture,
    run_update,
    update_collection,
    update_deps,
    update_repo,
    wants_tag_fetch,
    write_lock,
)
from mods import update as update_mod


def test_configured_ref_default_and_explicit() -> None:
    assert configured_ref({"id": "a", "repo": "x", "path": "p"}) == ("branch", "main")
    assert configured_ref({"id": "a", "repo": "x", "path": "p", "tag": "v1"}) == ("tag", "v1")


def test_configured_ref_rejects_multiple_refs() -> None:
    with pytest.raises(RuntimeError, match="only one of commit/tag/branch"):
        configured_ref({"id": "a", "repo": "x", "path": "p", "branch": "main", "tag": "v1"})


def test_resolve_dep_path_variants(env_factory) -> None:
    env: Env = env_factory()
    assert resolve_dep_path(env, "/abs/path") == Path("/abs/path")
    assert resolve_dep_path(env, "extras/tool") == env.zde_home / "extras/tool"
    assert resolve_dep_path(env, "home/project") == env.zde_home / "project"
    assert resolve_dep_path(env, "rel/project") == env.zde_root / "rel/project"


def test_build_lock_entry_includes_optional_sections(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from mods import update as update_mod

    monkeypatch.setattr(update_mod, "_is_git_tracked_file", lambda repo_path, rel_path: True)
    dep = {
        "id": "dep-a",
        "repo": "https://example.invalid/dep-a.git",
        "path": "home/dep-a",
        "aliases": ["dep-a", 123, "dep-a-alt"],
        "metadata": {"name": "Dep A"},
        "depends_on": ["dep-b"],
    }
    entry = build_lock_entry(
        dep=dep,
        ref_type="branch",
        ref_value="main",
        status="ok",
        updated_at="2026-01-01T00:00:00Z",
        current_commit_value="abc123",
        resolved_path=tmp_path / "dep-a",
    )
    assert entry["metadata"] == {"name": "Dep A"}
    assert entry["depends_on"] == ["dep-b"]
    assert entry["kernel_config"]["path"] == "os.conf"
    assert entry["kernel_config"]["aliases"] == ["dep-a", "dep-a-alt"]


def test_load_lock_missing_file_returns_default(tmp_path: Path) -> None:
    lock = load_lock(tmp_path / "deps-lock.yml")
    assert lock == {"version": 1, "dependencies": {}}


def test_run_and_run_capture_wrappers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(update_mod, "process_run", lambda cmd, cwd=None, **kwargs: 7)
    monkeypatch.setattr(update_mod, "process_run_capture", lambda cmd, cwd=None, **kwargs: "out")
    assert run(["x"]) == 7
    assert run_capture(["x"]) == "out"


def test_is_git_repo_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "repo"
    assert is_git_repo(path) is False
    path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(update_mod, "process_run_capture", lambda cmd, **kwargs: str(path))
    assert is_git_repo(path) is True
    monkeypatch.setattr(update_mod, "process_run_capture", lambda cmd, **kwargs: str(tmp_path))
    assert is_git_repo(path) is False

    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(128, "git")

    monkeypatch.setattr(update_mod, "process_run_capture", _raise)
    assert is_git_repo(path) is False


def test_is_git_repo_requires_own_worktree_root(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    outer.mkdir()
    subprocess.run(["git", "init", "-q", str(outer)], check=True)
    child = outer / "dependency"
    child.mkdir()

    assert is_git_repo(outer) is True
    assert is_git_repo(child) is False


def test_is_git_repo_accepts_git_file_worktrees_and_submodules(tmp_path: Path) -> None:
    source = tmp_path / "source"
    source.mkdir()
    subprocess.run(["git", "init", "-q", str(source)], check=True)
    (source / "tracked.txt").write_text("tracked", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "tracked.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=ZDE Test",
            "-c",
            "user.email=zde@example.invalid",
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )

    linked = tmp_path / "linked"
    subprocess.run(["git", "-C", str(source), "worktree", "add", "-q", str(linked), "-b", "linked"], check=True)
    assert (linked / ".git").is_file()
    assert is_git_repo(linked) is True

    parent = tmp_path / "parent"
    parent.mkdir()
    subprocess.run(["git", "init", "-q", str(parent)], check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "protocol.file.allow=always",
            "-C",
            str(parent),
            "submodule",
            "add",
            "-q",
            str(source),
            "dependency",
        ],
        check=True,
    )
    submodule = parent / "dependency"
    assert (submodule / ".git").is_file()
    assert is_git_repo(submodule) is True


def test_load_lock_yaml_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_file = tmp_path / "deps-lock.yml"
    lock_file.write_text("version: 1\n", encoding="utf-8")

    class _Yaml:
        @staticmethod
        def safe_load(_f):
            return {"version": 1, "dependencies": []}

    monkeypatch.setattr(update_mod, "yaml", _Yaml)
    lock = load_lock(lock_file)
    assert lock["dependencies"] == {}

    class _YamlBad:
        @staticmethod
        def safe_load(_f):
            return ["x"]

    monkeypatch.setattr(update_mod, "yaml", _YamlBad)
    with pytest.raises(RuntimeError, match="must be a YAML object"):
        load_lock(lock_file)


def test_load_lock_yq_fallback_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_file = tmp_path / "deps-lock.yml"
    lock_file.write_text("x", encoding="utf-8")
    monkeypatch.setattr(update_mod, "yaml", None)
    monkeypatch.setattr(update_mod, "process_run", lambda cmd, **kwargs: 1)
    with pytest.raises(RuntimeError, match="PyYAML or yq is required"):
        load_lock(lock_file)

    monkeypatch.setattr(update_mod, "process_run", lambda cmd, **kwargs: 0)

    def _raise_called(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "yq")

    monkeypatch.setattr(update_mod, "run_capture", _raise_called)
    with pytest.raises(RuntimeError, match="Failed to parse deps-lock.yml with yq"):
        load_lock(lock_file)

    monkeypatch.setattr(update_mod, "run_capture", lambda cmd: "{")
    with pytest.raises(RuntimeError, match="invalid JSON"):
        load_lock(lock_file)

    monkeypatch.setattr(update_mod, "run_capture", lambda cmd: json.dumps({"dependencies": {"a": {}}}))
    lock = load_lock(lock_file)
    assert lock["dependencies"] == {"a": {}}


def test_current_commit_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    assert current_commit(repo) is None
    (repo / ".git").mkdir()
    monkeypatch.setattr(update_mod, "run_capture", lambda cmd: "abc")
    assert current_commit(repo) == "abc"

    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(update_mod, "run_capture", _raise)
    assert current_commit(repo) is None


def test_write_lock_yaml_and_yq_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_file = tmp_path / "deps-lock.yml"
    payload = {"version": 1, "dependencies": {"a": {}}}

    class _Yaml:
        @staticmethod
        def safe_dump(lock, f, sort_keys=True):
            f.write("ok: true\n")

    monkeypatch.setattr(update_mod, "yaml", _Yaml)
    write_lock(lock_file, payload)
    assert lock_file.read_text(encoding="utf-8") == "ok: true\n"

    monkeypatch.setattr(update_mod, "yaml", None)
    monkeypatch.setattr(update_mod, "process_run", lambda cmd, **kwargs: 1)
    with pytest.raises(RuntimeError, match="PyYAML or yq is required"):
        write_lock(lock_file, payload)

    monkeypatch.setattr(update_mod, "process_run", lambda cmd, **kwargs: 0)

    def _raise_called(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "yq")

    monkeypatch.setattr(update_mod, "process_run_capture", _raise_called)
    with pytest.raises(RuntimeError, match="Failed to serialise lock file with yq"):
        write_lock(lock_file, payload)

    monkeypatch.setattr(update_mod, "process_run_capture", lambda cmd, input_text=None: "a: b")
    write_lock(lock_file, payload)
    assert lock_file.read_text(encoding="utf-8") == "a: b\n"


def test_write_lock_failure_preserves_previous_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock_file = tmp_path / "deps-lock.yml"
    lock_file.write_text("working: lock\n", encoding="utf-8")

    class _BrokenYaml:
        @staticmethod
        def safe_dump(lock, output, sort_keys=True):
            output.write("partial:")
            raise OSError("disk full")

    monkeypatch.setattr(update_mod, "yaml", _BrokenYaml)

    with pytest.raises(OSError, match="disk full"):
        write_lock(lock_file, {"dependencies": {}})

    assert lock_file.read_text(encoding="utf-8") == "working: lock\n"
    assert not list(tmp_path.glob(".deps-lock.yml.*"))


def test_wants_tag_fetch() -> None:
    assert wants_tag_fetch({"tag": True}) is True
    assert wants_tag_fetch({"tag": "v1"}) is False
    assert configured_ref({"id": "a", "repo": "x", "path": "p", "commit": "deadbeef"}) == ("commit", "deadbeef")


def test_ensure_origin_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "r"
    repo.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(update_mod, "run_capture", lambda cmd: "https://x")
    assert ensure_origin(repo, "https://x") == 0

    monkeypatch.setattr(update_mod, "run_capture", lambda cmd: "https://y")
    calls: list[list[str]] = []
    monkeypatch.setattr(update_mod, "run", lambda cmd, cwd=None: calls.append(cmd) or 0)
    assert ensure_origin(repo, "https://x") == 0
    assert "set-url" in calls[-1]

    def _raise(*args, **kwargs):
        raise subprocess.CalledProcessError(1, "git")

    monkeypatch.setattr(update_mod, "run_capture", _raise)
    calls.clear()
    assert ensure_origin(repo, "https://x") == 0
    assert "add" in calls[-1]


def test_clone_repo_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    calls: list[list[str]] = []

    def _run(cmd, cwd=None):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(update_mod, "run", _run)
    assert clone_repo(repo, "https://x", "branch", "main") == 0
    assert clone_repo(repo, "https://x", "tag", "v1", fetch_tags=True) == 0
    assert any("--tags" in c for c in calls)

    def _run_fail_first(cmd, cwd=None):
        return 2 if cmd[:2] == ["git", "clone"] else 0

    monkeypatch.setattr(update_mod, "run", _run_fail_first)
    assert clone_repo(repo, "https://x", "branch", "main") == 2
    assert clone_repo(repo, "https://x", "commit", "deadbeef") == 2

    sequence: list[int] = [0, 3, 0, 0]

    def _run_seq(cmd, cwd=None):
        return sequence.pop(0)

    monkeypatch.setattr(update_mod, "run", _run_seq)
    assert clone_repo(repo, "https://x", "commit", "deadbeef") == 3

    sequence = [0, 0, 4, 0]
    monkeypatch.setattr(update_mod, "run", _run_seq)
    assert clone_repo(repo, "https://x", "commit", "deadbeef") == 4

    sequence = [0, 0, 0, 0]
    monkeypatch.setattr(update_mod, "run", _run_seq)
    assert clone_repo(repo, "https://x", "commit", "deadbeef", fetch_tags=True) == 0
    sequence = [0, 0, 0]
    monkeypatch.setattr(update_mod, "run", _run_seq)
    assert clone_repo(repo, "https://x", "commit", "deadbeef") == 0


def test_update_repo_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    assert update_repo(repo, "https://x", "branch", "main") == 1
    (repo / ".git").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(update_mod, "ensure_origin", lambda path, url: 9)
    assert update_repo(repo, "https://x", "branch", "main") == 9

    monkeypatch.setattr(update_mod, "ensure_origin", lambda path, url: 0)
    calls: list[list[str]] = []
    seq = [0, 1, 0, 0]

    def _run_branch(cmd, cwd=None):
        calls.append(cmd)
        return seq.pop(0)

    monkeypatch.setattr(update_mod, "run", _run_branch)
    assert update_repo(repo, "https://x", "branch", "main") == 0
    assert calls[0][-2:] == [
        "origin",
        "+refs/heads/main:refs/remotes/origin/main",
    ]
    assert calls[-1][-3:] == ["merge", "--ff-only", "refs/remotes/origin/main"]

    seq = [8]
    monkeypatch.setattr(update_mod, "run", _run_branch)
    assert update_repo(repo, "https://x", "branch", "main") == 8

    seq = [0, 1, 2]
    monkeypatch.setattr(update_mod, "run", _run_branch)
    assert update_repo(repo, "https://x", "branch", "main") == 2

    seq = [0, 0, 3]
    monkeypatch.setattr(update_mod, "run", _run_branch)
    assert update_repo(repo, "https://x", "branch", "main") == 3

    seq = [0, 0, 0, 0]
    monkeypatch.setattr(update_mod, "run", _run_branch)
    assert update_repo(repo, "https://x", "branch", "main", fetch_tags=True) == 0

    seq = [4]

    def _run_tag(cmd, cwd=None):
        return seq.pop(0)

    monkeypatch.setattr(update_mod, "run", _run_tag)
    assert update_repo(repo, "https://x", "tag", "v1") == 4

    seq = [0, 5]
    monkeypatch.setattr(update_mod, "run", _run_tag)
    assert update_repo(repo, "https://x", "tag", "v1") == 5

    seq = [0, 0]
    monkeypatch.setattr(update_mod, "run", _run_tag)
    assert update_repo(repo, "https://x", "tag", "v1") == 0

    seq = [0, 0, 0]
    monkeypatch.setattr(update_mod, "run", _run_tag)
    assert update_repo(repo, "https://x", "tag", "v1", fetch_tags=True) == 0

    seq = [6]

    def _run_commit(cmd, cwd=None):
        return seq.pop(0)

    monkeypatch.setattr(update_mod, "run", _run_commit)
    assert update_repo(repo, "https://x", "commit", "deadbeef") == 6
    seq = [0, 7]
    monkeypatch.setattr(update_mod, "run", _run_commit)
    assert update_repo(repo, "https://x", "commit", "deadbeef") == 7
    seq = [0, 0, 0]
    monkeypatch.setattr(update_mod, "run", _run_commit)
    assert update_repo(repo, "https://x", "commit", "deadbeef", fetch_tags=True) == 0
    seq = [0, 0]
    monkeypatch.setattr(update_mod, "run", _run_commit)
    assert update_repo(repo, "https://x", "commit", "deadbeef") == 0


def test_update_repo_switches_branches_in_shallow_clone(tmp_path: Path) -> None:
    source = tmp_path / "source"
    checkout = tmp_path / "checkout"
    dirty_checkout = tmp_path / "dirty-checkout"

    subprocess.run(["git", "init", "-q", str(source)], check=True)
    subprocess.run(["git", "-C", str(source), "checkout", "-q", "-b", "main"], check=True)
    (source / "tracked.txt").write_text("main\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "tracked.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=ZDE Tests",
            "-c",
            "user.email=zde-tests@example.invalid",
            "commit",
            "-q",
            "-m",
            "main",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(source), "checkout", "-q", "-b", "next"], check=True)
    (source / "tracked.txt").write_text("next\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(source), "add", "tracked.txt"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(source),
            "-c",
            "user.name=ZDE Tests",
            "-c",
            "user.email=zde-tests@example.invalid",
            "commit",
            "-q",
            "-m",
            "next",
        ],
        check=True,
    )
    subprocess.run(["git", "-C", str(source), "checkout", "-q", "main"], check=True)

    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", "--branch", "main", source.as_uri(), str(checkout)],
        check=True,
    )
    remote_branches = subprocess.run(
        ["git", "-C", str(checkout), "branch", "--remotes"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "origin/next" not in remote_branches

    assert update_repo(checkout, source.as_uri(), "branch", "next") == 0
    assert run_capture(["git", "-C", str(checkout), "branch", "--show-current"]) == "next"
    assert (checkout / "tracked.txt").read_text(encoding="utf-8") == "next\n"

    subprocess.run(
        ["git", "clone", "-q", "--depth", "1", "--branch", "main", source.as_uri(), str(dirty_checkout)],
        check=True,
    )
    (dirty_checkout / "tracked.txt").write_text("local edit\n", encoding="utf-8")
    assert update_repo(dirty_checkout, source.as_uri(), "branch", "next") != 0
    assert run_capture(["git", "-C", str(dirty_checkout), "branch", "--show-current"]) == "main"
    assert (dirty_checkout / "tracked.txt").read_text(encoding="utf-8") == "local edit\n"


def test_resolve_env_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    zde_path = tmp_path / "zde-root"
    (zde_path / "home" / "zde").mkdir(parents=True, exist_ok=True)
    (zde_path / "home" / "zde" / "deps.yml").write_text("dependencies: []\n", encoding="utf-8")
    monkeypatch.setenv("ZDE_PATH", str(zde_path))
    monkeypatch.setenv("ZDE_USER_PATH", str(tmp_path / "user"))
    env = resolve_env()
    assert env.deps_file == zde_path / "home" / "zde" / "deps.yml"

    monkeypatch.delenv("ZDE_PATH", raising=False)
    fake_home = tmp_path / "home-zeal8bit"
    (fake_home / "zde").mkdir(parents=True, exist_ok=True)
    (fake_home / "zde" / "deps.yml").write_text("dependencies: []\n", encoding="utf-8")
    monkeypatch.setattr(update_mod.Path, "home", staticmethod(lambda: fake_home))
    # Force fallback path branch by making /home/zeal8bit/zde/deps.yml absent.
    env2 = resolve_env()
    assert env2.user_path == Path(str(tmp_path / "user"))

    # Cover fallback local path branch (lines 235-238) and missing file error.
    original_is_file = update_mod.Path.is_file

    def _fake_is_file(self: Path) -> bool:
        if self.name == "deps.yml":
            return False
        return original_is_file(self)

    monkeypatch.setattr(update_mod.Path, "is_file", _fake_is_file)
    with pytest.raises(FileNotFoundError, match="Missing dependency catalog"):
        resolve_env()


def test_is_git_tracked_file_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo = tmp_path / "repo"
    assert _is_git_tracked_file(repo, "x") is False
    repo.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(update_mod, "process_run", lambda cmd, **kwargs: 0)
    assert _is_git_tracked_file(repo, "x") is True
    monkeypatch.setattr(update_mod, "process_run", lambda cmd, **kwargs: 1)
    assert _is_git_tracked_file(repo, "x") is False


def test_build_lock_entry_optional_exclusions(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(update_mod, "_is_git_tracked_file", lambda repo_path, rel_path: False)
    dep = {"id": "dep-x", "repo": "r", "path": "p", "metadata": {}, "depends_on": []}
    entry = build_lock_entry(dep, "branch", "main", "ok", "now", None, tmp_path / "dep")
    assert "metadata" not in entry
    assert "depends_on" not in entry
    assert "kernel_config" not in entry


def test_update_deps_and_update_collection_and_run_update(env_factory, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    env: Env = env_factory()
    env.deps_file.write_text("dependencies: []\n", encoding="utf-8")
    fake_mod = ModuleType("mods.deps")

    class _Catalog:
        def __init__(self, passed_env):
            self.env = passed_env

        def sync_for_update(self) -> int:
            return 5

    fake_mod.DepCatalog = _Catalog  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mods.deps", fake_mod)
    assert update_deps(env) == 5

    class _Resp:
        def __init__(self, payload: bytes):
            self._payload = payload

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._payload

    def _raise_url(*args, **kwargs):
        raise update_mod.urllib.error.URLError("bad")

    monkeypatch.setattr(update_mod.urllib.request, "urlopen", _raise_url)
    assert update_collection(env) == 1

    monkeypatch.setattr(update_mod.urllib.request, "urlopen", lambda url: _Resp(b"\xff\xfe"))
    assert update_collection(env) == 1

    monkeypatch.setattr(update_mod.urllib.request, "urlopen", lambda url: _Resp(b"dependencies:\n  - bad\n"))
    monkeypatch.setattr(update_mod, "load_deps_yaml", lambda path: (_ for _ in ()).throw(RuntimeError("invalid")))
    assert update_collection(env) == 1

    monkeypatch.setattr(update_mod.urllib.request, "urlopen", lambda url: _Resp(b"dependencies: []"))
    monkeypatch.setattr(update_mod, "load_deps_yaml", lambda path: [])
    assert update_collection(env) == 0
    assert env.collection_file.read_text(encoding="utf-8").endswith("\n")
    assert "Collection catalog updated" in capsys.readouterr().out

    calls: list[str] = []
    monkeypatch.setattr(update_mod, "update_deps", lambda _env: calls.append("deps") or 7)
    monkeypatch.setattr(update_mod, "update_collection", lambda _env: calls.append("collection") or 0)
    assert run_update(env) == 7
    assert calls == ["collection", "deps"]
    calls.clear()
    monkeypatch.setattr(update_mod, "update_deps", lambda _env: 0)
    monkeypatch.setattr(update_mod, "update_collection", lambda _env: calls.append("collection") or 8)
    assert run_update(env) == 8
    assert calls == ["collection"]
    calls.clear()
    monkeypatch.setattr(update_mod, "update_collection", lambda _env: calls.append("collection") or 0)
    monkeypatch.setattr(update_mod, "update_deps", lambda _env: calls.append("deps") or 0)
    assert run_update(env) == 0
    assert calls == ["collection", "deps"]


def test_update_collection_rejects_invalid_merged_graph(env_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    env: Env = env_factory()
    env.deps_file.write_text(
        """dependencies:
  - id: a
    repo: https://example.invalid/a.git
  - id: b
    repo: https://example.invalid/b.git
""",
        encoding="utf-8",
    )
    env.collection_file.parent.mkdir(parents=True, exist_ok=True)
    env.collection_file.write_text("previous catalog\n", encoding="utf-8")
    payload = b"""dependencies:
  - id: a
    repo: https://example.invalid/a.git
    depends_on: [b]
  - id: b
    repo: https://example.invalid/b.git
    depends_on: [a]
"""

    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return payload

    monkeypatch.setattr(update_mod.urllib.request, "urlopen", lambda url: _Resp())

    assert update_collection(env) == 1
    assert env.collection_file.read_text(encoding="utf-8") == "previous catalog\n"


def test_yaml_import_fallback_branch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    source = Path(update_mod.__file__)
    original_import = builtins.__import__

    def _import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml":
            raise ModuleNotFoundError("yaml missing")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import)
    monkeypatch.setenv("ZDE_USER_PATH", str(tmp_path / "user"))
    spec = importlib.util.spec_from_file_location("mods_update_yaml_fallback", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    assert module.yaml is None
