from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest

from mods.deps import Dep, DepCatalog
from mods.update import Env


def _write_yaml(path: Path, text: str) -> None:
    path.write_text(text.strip() + "\n", encoding="utf-8")


def _make_env(tmp_path: Path) -> Env:
    root = tmp_path / "root"
    home = tmp_path / "home"
    user = tmp_path / "user"
    root.mkdir(parents=True, exist_ok=True)
    home.mkdir(parents=True, exist_ok=True)
    user.mkdir(parents=True, exist_ok=True)
    return Env(
        zde_root=root,
        zde_home=home,
        user_path=user,
        deps_file=tmp_path / "deps.yml",
        lock_file=user / "deps-lock.yml",
        collection_file=user / "collection.yml",
        managed_env_file=user / "deps.env",
    )


def _fake_catalog(tmp_path: Path, *, installed_by_id: dict[str, bool], lock_deps: dict[str, object] | None = None):
    env = _make_env(tmp_path)
    by_id: dict[str, Dep] = {}
    return SimpleNamespace(
        env=env,
        installed_by_id=installed_by_id,
        lock_deps=lock_deps or {},
        by_id=by_id,
        _infer_build_tool=lambda dep: "make",
    )


def test_dep_state_variants_and_markers(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": False, "dep-b": False})
    dep_a = Dep(catalog, {"id": "dep-a", "repo": "x", "path": "extras/dep-a", "required": True})
    assert dep_a.state == "required-miss"
    assert dep_a.marker == "[?]"

    catalog = _fake_catalog(
        tmp_path,
        installed_by_id={"dep-a": True, "dep-b": False},
        lock_deps={"dep-a": {"status": "synced"}},
    )
    dep_b = Dep(catalog, {"id": "dep-b", "repo": "x", "path": "extras/dep-b", "aliases": ["B"]})
    catalog.by_id["dep-b"] = dep_b
    dep_a = Dep(catalog, {"id": "dep-a", "repo": "x", "path": "extras/dep-a", "depends_on": ["dep-b"]})
    catalog.by_id["dep-a"] = dep_a
    assert dep_a.state == "broken(B)"
    assert dep_a.has_error is True

    catalog.installed_by_id["dep-b"] = True
    assert dep_a.state == "ok"
    assert dep_a.marker == "[x]"

    catalog.lock_deps = {}
    assert dep_a.state == "untracked"


def test_dep_env_exports_runtime_paths_and_media(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True})
    dep = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "home/dep-a",
            "env": [
                "DEP_ROOT",
                {"name": "DEP_BIN", "path": "bin", "add_to_path": [".", "bin"]},
            ],
            "metadata": {
                "screenshot": ["https://example.invalid/shot.png"],
                "video": "https://example.invalid/video.mp4",
            },
        },
    )
    assert dep.has_media is True
    assert dep.screenshot_urls == ["https://example.invalid/shot.png"]
    assert dep.video_urls == ["https://example.invalid/video.mp4"]

    exposed = dict(dep.exposed_env())
    runtime = dict(dep.runtime_env())
    assert exposed["DEP_ROOT"].endswith("/home/dep-a")
    assert exposed["DEP_BIN"].endswith("/home/dep-a/bin")
    assert runtime["DEP_ROOT"].endswith("/home/dep-a")
    assert runtime["DEP_BIN"].endswith("/home/dep-a/bin")
    assert any(path.endswith("/home/dep-a") for path in dep.env_export_paths())
    assert any(path.endswith("/home/dep-a/bin") for path in dep.runtime_paths())


def test_dep_stage_success_with_bin_rename_and_missing_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True})
    dep_dir = catalog.env.zde_home / "dep-a"
    (dep_dir / "bin").mkdir(parents=True, exist_ok=True)
    (dep_dir / "bin" / "program.bin").write_text("x", encoding="utf-8")

    dep = Dep(
        catalog,
        {"id": "dep-a", "repo": "x", "path": "home/dep-a", "metadata": {"category": ["game"]}},
    )

    staged: dict[str, object] = {}

    class _FakeImage:
        image_type = "cf"

        def stage_artifacts(self, artifact_paths, stage_root: str = "/apps") -> None:
            staged["artifact_paths"] = artifact_paths
            staged["stage_root"] = stage_root

    monkeypatch.setattr("mods.deps.get_rename_bins_config", lambda: True)
    rc = dep.stage(_FakeImage())
    assert rc == 0
    assert staged["stage_root"] == "/games"
    artifact_paths = staged["artifact_paths"]
    assert len(artifact_paths) == 1
    assert artifact_paths[0][1].name == "program"

    dep_missing = Dep(
        catalog,
        {
            "id": "dep-b",
            "repo": "x",
            "path": "home/dep-a",
            "build": {"artifacts": ["missing.bin"]},
        },
    )
    rc = dep_missing.stage(_FakeImage())
    assert rc == 1


def test_depcatalog_resolve_and_dependency_chain(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: OrgA/tool
            repo: https://example.invalid/a.git
          - id: OrgB/tool
            repo: https://example.invalid/b.git
          - id: app
            repo: https://example.invalid/app.git
            depends_on: [OrgA/tool]
            aliases: [main-app]
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)

    catalog = DepCatalog(env)
    assert catalog.resolve("main-app") is not None
    assert catalog.resolve("app").id == "app"
    with pytest.raises(RuntimeError, match="Ambiguous dependency identifier 'tool'"):
        catalog.resolve("tool")
    assert catalog.dependency_chain("app") == ["OrgA/tool", "app"]


def test_depcatalog_dependency_chain_cycle_and_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: a
            repo: https://example.invalid/a.git
            depends_on: [b]
          - id: b
            repo: https://example.invalid/b.git
            depends_on: [a]
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    with pytest.raises(RuntimeError, match="Dependency cycle detected"):
        DepCatalog(env)

    env2 = _make_env(tmp_path / "other")
    _write_yaml(
        env2.deps_file,
        """
        dependencies:
          - id: root
            repo: https://example.invalid/root.git
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    catalog = DepCatalog(env2)
    with pytest.raises(RuntimeError, match="Unknown dependency id in chain: missing"):
        catalog.dependency_chain("missing")


def test_depcatalog_build_command_env_collects_runtime_exports_and_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: https://example.invalid/a.git
            path: home/dep-a
            env:
              - name: DEP_A
                path: .
                add_to_path: [bin]
          - id: dep-b
            repo: https://example.invalid/b.git
            path: extras/dep-b
            env:
              - name: DEP_B
                path: tools
                add_to_path: [tools]
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: p.as_posix().endswith("dep-a"))
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("Z88DK_PATH", "/opt/z88dk")
    monkeypatch.setenv("SDCC_PATH", "/opt/sdcc")
    monkeypatch.setenv("GNUAS_PATH", "/opt/gnu-as")

    catalog = DepCatalog(env)
    build_env = catalog._build_command_env()
    assert build_env["DEP_A"].endswith("/home/dep-a")
    assert "DEP_B" not in build_env
    path_parts = build_env["PATH"].split(":")
    assert "/opt/z88dk/bin" in path_parts
    assert "/opt/sdcc/bin" in path_parts
    assert "/opt/gnu-as/bin" in path_parts
    assert any(part.endswith("/home/dep-a/bin") for part in path_parts)


def test_top_level_config_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    class _Cfg:
        def get(self, key: str):
            calls["get"] = key
            return True

        def set(self, key: str, value: object):
            calls["set"] = (key, value)

        def save(self):
            calls["save"] = True

    monkeypatch.setattr("mods.deps.Config.load", lambda: _Cfg())
    from mods import deps as deps_mod

    assert deps_mod.get_skip_sync_installed_config() is True
    assert deps_mod.get_rename_bins_config() is True
    deps_mod.set_skip_sync_installed_config(False)
    assert calls["set"] == ("deps.skip-sync-installed", False)
    assert calls["save"] is True


def test_dep_misc_property_fallbacks_and_wrappers(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": False})
    catalog.install_dep = lambda dep_id: 11
    catalog.remove_dep = lambda dep_id, force=False: 12
    catalog.build_dep = lambda dep_id: 13
    catalog.update_dep = lambda dep_id: 14

    dep = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "extras/dep-a",
            "aliases": "bad",
            "depends_on": "bad",
            "metadata": "bad",
            "build": {"stage": False},
        },
    )
    assert dep.aliases == []
    assert dep.depends_on == []
    assert dep.categories == ["Other"]
    assert dep.display_name == "dep-a"
    assert dep.stage_disabled is True
    assert dep.install() == 11
    assert dep.remove(force=True) == 12
    assert dep.build() == 13
    assert dep.update() == 14


def test_dep_inferred_stage_root_and_artifact_paths_branches(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True})
    dep_dir = catalog.env.zde_home / "dep-a"
    dep_dir.mkdir(parents=True, exist_ok=True)
    (dep_dir / "CMakeLists.txt").write_text("x", encoding="utf-8")
    (dep_dir / "bin").mkdir(exist_ok=True)
    (dep_dir / "bin" / "Makefile").write_text("x", encoding="utf-8")
    (dep_dir / "bin" / "program.bin").write_text("x", encoding="utf-8")

    dep = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "home/dep-a",
            "metadata": {"category": ["demo"]},
            "build": {"artifacts": ["bin/program.bin", "bin/"]},
        },
    )
    assert dep.inferred_stage_root == "/demos"
    artifact_paths = dep.artifact_paths()
    assert len(artifact_paths) == 2

    dep2 = Dep(catalog, {"id": "dep-b", "repo": "x", "path": "home/dep-a", "build": 123})
    assert dep2.artifact_paths() == []


def test_dep_env_items_invalid_entries_filtered(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True})
    dep = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "home/dep-a",
            "env": [
                "",
                {"name": "", "path": "."},
                {"name": "A", "path": 1},
                {"name": "B", "path": "", "add_to_path": [1, "", "bin"]},
                123,
            ],
        },
    )
    items = dep._env_items()
    assert items == [{"name": "B", "path": ".", "add_to_path": ["bin"]}]


def test_dep_render_info_nested_values(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": False})
    dep = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "home/dep-a",
            "build": {"commands": ["echo hi"]},
            "metadata": {"name": "Dep A"},
            "depends_on": [],
        },
    )
    rendered = dep.render_info()
    assert "Id: dep-a" in rendered
    assert "Build:" in rendered
    assert "- echo hi" in rendered


def test_depcatalog_init_with_collection_merge_branch(env_factory, fs_builder, monkeypatch: pytest.MonkeyPatch) -> None:
    env = env_factory()
    fs_builder.write_yaml(
        str(env.deps_file.relative_to(fs_builder.root)),
        """
        dependencies:
          - id: dep-a
            repo: https://example.invalid/a.git
        """,
    )
    fs_builder.write_yaml(
        str(env.collection_file.relative_to(fs_builder.root)),
        """
        dependencies:
          - id: dep-b
            repo: https://example.invalid/b.git
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    merged_called = {"ok": False}

    def _merge(primary, secondary):
        merged_called["ok"] = True
        return [*primary, *secondary]

    monkeypatch.setattr("mods.deps.merge_deps_lists", _merge)
    catalog = DepCatalog(env)
    assert merged_called["ok"] is True
    assert set(catalog.by_id.keys()) == {"dep-a", "dep-b"}


def test_depcatalog_misc_getters_and_repo_name(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: org/dep-a
            repo: x
            metadata:
              category: installed
          - id: dep-b
            repo: y
            metadata:
              category: game
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {"org/dep-a": {}}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: p.as_posix().endswith("dep-a"))
    cat = DepCatalog(env)
    assert cat.get("missing") is None
    assert cat.installed()[0].id == "org/dep-a"
    assert "installed" in cat.categories
    assert cat.category("").__class__ is list
    assert DepCatalog._repo_name_from_id("org/repo") == "repo"
    assert DepCatalog._repo_name_from_id("repo") == "repo"


def test_depcatalog_refresh_handles_non_dict_lockdeps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": []})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    cat = DepCatalog(env)
    assert cat.lock_deps == {}


def test_get_dependents_and_remove_dep_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: core
            repo: x
            required: true
          - id: app
            repo: y
            depends_on: [core]
          - id: opt
            repo: z
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: p.as_posix().endswith("app") or p.as_posix().endswith("opt"))
    cat = DepCatalog(env)
    assert cat.get_dependents("core") == ["app"]
    assert cat.remove_dep("core") == 1
    assert "Cannot remove required dependency" in capsys.readouterr().out
    assert cat.remove_dep("opt") == 0


def test_build_dep_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            build: false
          - id: dep-b
            repo: y
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: p.as_posix().endswith("dep-a"))
    monkeypatch.setattr("mods.requirements.require_deps", lambda ids: True)
    cat = DepCatalog(env)

    # build disabled
    monkeypatch.setattr(cat, "_write_dep_lock_entry", lambda dep, status: None)
    assert cat.build_dep("dep-a") == 0
    assert "Build disabled for dependency" in capsys.readouterr().out

    # not installed
    assert cat.build_dep("dep-b") == 1

    # no build configured
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: True)
    monkeypatch.setattr(cat, "_infer_build_tool", lambda dep: None)
    assert cat.build_dep("dep-b") == 0

    # build failure then success
    monkeypatch.setattr(cat, "_infer_build_tool", lambda dep: "make")
    monkeypatch.setattr(cat, "_run_build_for_dep", lambda dep: 5)
    assert cat.build_dep("dep-b") == 5
    monkeypatch.setattr(cat, "_run_build_for_dep", lambda dep: 0)
    assert cat.build_dep("dep-b") == 0


def test_update_dep_sync_fail_and_build_fail(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    monkeypatch.setattr("mods.deps.clone_repo", lambda *args, **kwargs: 3)
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_write_dep_lock_entry", lambda dep, status: None)
    assert cat.update_dep("dep-a") == 3

    monkeypatch.setattr("mods.deps.clone_repo", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cat, "_run_build_for_dep", lambda dep: 7)
    monkeypatch.setattr(cat, "_write_managed_env_file", lambda: None)
    assert cat.update_dep("dep-a") == 7


def test_sync_for_update_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: req
            repo: x
            required: true
          - id: opt
            repo: y
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: p.as_posix().endswith("req"))
    monkeypatch.setattr("mods.deps.get_skip_sync_installed_config", lambda: True)
    monkeypatch.setattr("mods.deps.build_lock_entry", lambda **kwargs: {"status": kwargs["status"]})
    monkeypatch.setattr("mods.deps.current_commit", lambda p: "abc")
    writes: list[dict[str, object]] = []
    monkeypatch.setattr("mods.deps.write_lock", lambda path, lock: writes.append(lock.copy()))
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_write_managed_env_file", lambda: None)
    assert cat.sync_for_update() == 0
    assert writes


def test_prune_write_env_and_lock_helpers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
            env:
              - name: DEP_A
                path: .
                add_to_path: [bin, bin]
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: True)
    cat = DepCatalog(env)
    dep = cat.by_id["dep-a"]

    # prune outside roots no-op
    outside = tmp_path / "outside" / "x"
    outside.parent.mkdir(parents=True, exist_ok=True)
    outside.write_text("x", encoding="utf-8")
    cat._prune_empty_parent_dirs(outside)

    # managed env file
    cat._write_managed_env_file()
    assert env.managed_env_file.is_file()
    content = env.managed_env_file.read_text(encoding="utf-8")
    assert "DEP_A=" in content
    assert "ZDE_DEP_PATHS=" in content

    # write lock entry / remove lock entry
    lock_store = {"dependencies": []}
    monkeypatch.setattr("mods.deps.load_lock", lambda _: lock_store)
    monkeypatch.setattr("mods.deps.write_lock", lambda path, lock: None)
    monkeypatch.setattr("mods.deps.current_commit", lambda p: "abc")
    monkeypatch.setattr("mods.deps.build_lock_entry", lambda **kwargs: {"id": kwargs["dep"]["id"]})
    cat._write_dep_lock_entry(dep, "synced")
    cat._remove_dep_lock_entry(dep.id)


def test_run_build_for_dep_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
        """,
    )
    dep_dir = env.zde_home / "dep-a"
    dep_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: True)
    cat = DepCatalog(env)
    dep = cat.by_id["dep-a"]

    assert cat._run_build_for_dep(Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": False})) == 0
    assert cat._run_build_for_dep(Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": "bad"})) == 1

    monkeypatch.setattr(cat, "_infer_build_tool", lambda d: None)
    assert cat._run_build_for_dep(Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a"})) == 0

    # commands invalid
    assert cat._run_build_for_dep(Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": {"commands": []}})) == 1

    # commands success/fail
    monkeypatch.setattr("mods.deps.subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    assert (
        cat._run_build_for_dep(
            Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": {"commands": ["echo hi"]}})
        )
        == 0
    )
    monkeypatch.setattr("mods.deps.subprocess.run", lambda *args, **kwargs: SimpleNamespace(returncode=9))
    assert (
        cat._run_build_for_dep(
            Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": {"commands": ["echo hi"]}})
        )
        == 9
    )

    # tool branches
    monkeypatch.setattr(cat, "_build_command_env", lambda: os.environ.copy())
    monkeypatch.setattr("cmds.cmake.main", lambda args: 0)
    monkeypatch.setattr("cmds.make.main", lambda args: 0)
    assert cat._run_build_for_dep(Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": {"tool": "cmake"}})) == 0
    assert cat._run_build_for_dep(Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": {"tool": "make"}})) == 0
    assert cat._run_build_for_dep(Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": {"tool": "bad"}})) == 1
    assert cat._run_build_for_dep(Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": {"tool": "make", "args": [1]}})) == 1
    assert cat._run_build_for_dep(Dep(cat, {"id": "x", "repo": "r", "path": "home/dep-a", "build": {"tool": "make", "args": "bad"}})) == 1


def test_load_catalog_and_load_deps_wrappers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
        """,
    )
    monkeypatch.setattr("mods.deps.resolve_env", lambda: env)
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    from mods import deps as deps_mod

    cat = deps_mod.load_catalog()
    assert isinstance(cat, DepCatalog)
    deps = deps_mod.load_deps()
    assert deps and deps[0].id == "dep-a"


def test_dep_misc_uncovered_property_branches(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": False})
    dep = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "/outside/dep-a",
            "metadata": {"screenshot": 1, "video": [1, " "]},
        },
    )
    assert dep.env_export_base_path == Path("/outside/dep-a")
    assert dep.screenshot_urls == []
    assert dep.video_urls == []
    assert dep.preferred_label == "dep-a"
    assert dep.marker == "[ ]"
    assert dep.display_name == "dep-a"
    with pytest.raises(AttributeError):
        _ = dep.missing_attr


def test_dep_stage_disabled_and_no_artifacts_messages(tmp_path: Path, capsys) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True})
    dep_disabled = Dep(catalog, {"id": "dep-a", "repo": "x", "path": "home/dep-a", "build": False})
    rc = dep_disabled.stage(SimpleNamespace(image_type="cf", stage_artifacts=lambda *args, **kwargs: None))
    assert rc == 1
    assert "Build disabled for dependency" in capsys.readouterr().out

    dep_no_artifacts = Dep(catalog, {"id": "dep-b", "repo": "x", "path": "home/dep-a", "build": {"stage": False}})
    rc = dep_no_artifacts.stage(SimpleNamespace(image_type="cf", stage_artifacts=lambda *args, **kwargs: None))
    assert rc == 1
    assert "Staging disabled for dependency" in capsys.readouterr().out


def test_install_dep_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
        """,
    )
    dep_path = env.zde_home / "dep-a"
    dep_path.mkdir(parents=True, exist_ok=True)
    (dep_path / "existing.txt").write_text("x", encoding="utf-8")

    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.configured_ref", lambda raw: ("branch", "main"))
    monkeypatch.setattr("mods.deps.wants_tag_fetch", lambda raw: False)
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: False)
    monkeypatch.setattr("mods.deps.migrate_broken_submodule_checkout", lambda *args, **kwargs: None)
    cat = DepCatalog(env)
    assert cat.install_dep("dep-a", include_dependencies=False) == 1
    assert "exists but is not a git repo" in capsys.readouterr().out

    # update existing repo path (has_git=True) failure then success
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: True)
    monkeypatch.setattr("mods.deps.update_repo", lambda *args, **kwargs: 5)
    lock_calls: list[str] = []
    monkeypatch.setattr(cat, "_write_dep_lock_entry", lambda dep, status: lock_calls.append(status))
    assert cat.install_dep("dep-a", include_dependencies=False) == 5
    assert lock_calls[-1] == "sync_failed"

    monkeypatch.setattr("mods.deps.update_repo", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cat, "_write_managed_env_file", lambda: None)
    assert cat.install_dep("dep-a", include_dependencies=False) == 0

    # fresh clone fail then build fail then success
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: False)
    if dep_path.exists():
        import shutil

        shutil.rmtree(dep_path)
    def _clone_fail(path, repo, ref_type, ref_value, *, fetch_tags=False):
        Path(path).mkdir(parents=True, exist_ok=True)
        (Path(path) / "partial").write_text("x", encoding="utf-8")
        return 9

    monkeypatch.setattr("mods.deps.clone_repo", _clone_fail)
    prune_calls = {"count": 0}
    monkeypatch.setattr(cat, "_prune_empty_parent_dirs", lambda p: prune_calls.__setitem__("count", prune_calls["count"] + 1))
    assert cat.install_dep("dep-a", include_dependencies=False) == 9

    monkeypatch.setattr("mods.deps.clone_repo", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cat, "_run_build_for_dep", lambda dep: 7)
    assert cat.install_dep("dep-a", include_dependencies=False) == 7
    monkeypatch.setattr(cat, "_run_build_for_dep", lambda dep: 0)
    assert cat.install_dep("dep-a", include_dependencies=False) == 0


def test_remove_dep_dependents_and_file_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
          - id: dep-b
            repo: y
            path: home/dep-b
            depends_on: [dep-a]
        """,
    )
    path_a = env.zde_home / "dep-a"
    path_b = env.zde_home / "dep-b"
    path_a.parent.mkdir(parents=True, exist_ok=True)
    path_a.write_text("x", encoding="utf-8")
    path_b.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: True)
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_remove_dep_lock_entry", lambda dep_id: None)
    monkeypatch.setattr(cat, "refresh", lambda: None)
    assert cat.remove_dep("dep-a", force=False) == 1
    assert "required by dep-b" in capsys.readouterr().out
    assert cat.remove_dep("dep-a", force=True) == 0


def test_build_dep_require_deps_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.requirements.require_deps", lambda ids: False)
    cat = DepCatalog(env)
    assert cat.build_dep("dep-a") == 1


def test_update_dep_branches_for_non_git_and_existing_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
        """,
    )
    path_a = env.zde_home / "dep-a"
    path_a.mkdir(parents=True, exist_ok=True)
    (path_a / "file.txt").write_text("x", encoding="utf-8")

    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.configured_ref", lambda raw: ("branch", "main"))
    monkeypatch.setattr("mods.deps.wants_tag_fetch", lambda raw: False)
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: False)
    monkeypatch.setattr("mods.deps.migrate_broken_submodule_checkout", lambda *args, **kwargs: None)
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_write_dep_lock_entry", lambda dep, status: None)
    monkeypatch.setattr(cat, "_write_managed_env_file", lambda: None)
    assert cat.update_dep("dep-a", include_dependencies=False) == 1
    assert "exists but is not a git repo" in capsys.readouterr().out

    # existing git path update success path
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: True)
    monkeypatch.setattr("mods.deps.update_repo", lambda *args, **kwargs: 0)
    assert cat.update_dep("dep-a", include_dependencies=False) == 0

    # existing git path sync fail path
    monkeypatch.setattr("mods.deps.update_repo", lambda *args, **kwargs: 6)
    assert cat.update_dep("dep-a", include_dependencies=False) == 6


def test_sync_for_update_error_and_build_fail_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: req
            repo: x
            required: true
            path: home/req
          - id: opt
            repo: y
            path: home/opt
        """,
    )
    req_path = env.zde_home / "req"
    req_path.mkdir(parents=True, exist_ok=True)
    (req_path / "file.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.configured_ref", lambda raw: ("branch", "main"))
    monkeypatch.setattr("mods.deps.wants_tag_fetch", lambda raw: False)
    monkeypatch.setattr("mods.deps.get_skip_sync_installed_config", lambda: False)
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: False)
    writes: list[dict[str, object]] = []
    monkeypatch.setattr("mods.deps.write_lock", lambda path, lock: writes.append(dict(lock)))
    cat = DepCatalog(env)
    assert cat.sync_for_update() == 1
    assert writes
    assert "exists but is not a git repo" in capsys.readouterr().err

    # clean required dir then hit clone + build fail for newly installed
    import shutil

    shutil.rmtree(req_path)
    monkeypatch.setattr("mods.deps.clone_repo", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cat, "_run_build_for_dep", lambda dep: 8)
    monkeypatch.setattr(cat, "_write_managed_env_file", lambda: None)
    monkeypatch.setattr("mods.deps.build_lock_entry", lambda **kwargs: {"status": kwargs["status"]})
    monkeypatch.setattr("mods.deps.current_commit", lambda p: "abc")
    assert cat.sync_for_update() == 8


def test_prune_and_infer_build_tool_edges(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
        """,
    )
    dep_path = env.zde_home / "dep-a"
    dep_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    cat = DepCatalog(env)
    cat._prune_empty_parent_dirs(dep_path / "child")
    dep_path.mkdir(parents=True, exist_ok=True)
    assert cat._infer_build_tool(cat.by_id["dep-a"]) is None
    (dep_path / "Makefile").write_text("x", encoding="utf-8")
    assert cat._infer_build_tool(cat.by_id["dep-a"]) == "make"
    (dep_path / "CMakeLists.txt").write_text("x", encoding="utf-8")
    assert cat._infer_build_tool(cat.by_id["dep-a"]) == "cmake"


def test_dep_remaining_property_and_artifact_branches(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True})
    dep_dir = catalog.env.zde_home / "dep-a"
    (dep_dir / "build").mkdir(parents=True, exist_ok=True)
    (dep_dir / "build" / "manifest").write_text("x", encoding="utf-8")
    (dep_dir / "build" / "keep").write_text("x", encoding="utf-8")
    (dep_dir / "build" / "x.bin").write_text("x", encoding="utf-8")
    (dep_dir / "build" / "subdir").mkdir(exist_ok=True)

    dep = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "home/dep-a",
            "custom": 7,
            "metadata": {"category": [], "name": "Pretty"},
            "build": {"root": " /custom ", "artifacts": [None, "  ", "build/x.bin", "/abs/path/"]},
        },
    )
    assert dep.custom == 7
    assert dep.categories[0] == "Other"
    assert dep._metadata_url_list("missing") == []
    dep_bad_meta = Dep(catalog, {"id": "b", "repo": "x", "path": "home/dep-a", "metadata": 123})
    assert dep_bad_meta._metadata_url_list("screenshot") == []
    assert dep.preferred_label == "dep-a"
    assert dep.display_name == "Pretty (dep-a)"
    assert dep.inferred_stage_root == "/custom"
    inferred = dep._infer_default_artifacts()
    assert "build/x.bin" in inferred
    assert "build/keep" in inferred
    assert "build/manifest" not in inferred
    arts = dep.artifact_paths()
    assert len(arts) == 2
    assert arts[1][1] == Path(".")

    dep_stage = Dep(catalog, {"id": "s", "repo": "x", "path": "home/dep-a", "build": {"artifacts": []}})
    rc = dep_stage.stage(SimpleNamespace(image_type="cf", stage_artifacts=lambda *args, **kwargs: None))
    assert rc == 1


def test_dep_state_broken_deps_without_labels(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True, "unknown": False}, lock_deps={"dep-a": {}})
    dep = Dep(catalog, {"id": "dep-a", "repo": "x", "path": "home/dep-a", "depends_on": ["unknown"]})
    assert dep.state == "broken-deps"


def test_dep_render_info_deep_value_branches(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True}, lock_deps={"dep-a": {}})
    dep = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "home/dep-a",
            "metadata": {"name": "Dep", "empty": {}},
            "matrix": [[1, 2], {"k": {"nested": []}}],
            "raw": 5,
        },
    )
    rendered = dep.render_info()
    assert "Matrix:" in rendered
    assert "Raw: 5" in rendered
    assert "Empty:" in rendered


def test_category_resolve_dependency_chain_extra_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            metadata:
              category: game
            aliases: [A]
          - id: dep-b
            repo: y
            depends_on: [dep-c, dep-c]
          - id: dep-c
            repo: z
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    cat = DepCatalog(env)
    assert cat.category("game")[0].id == "dep-a"
    assert cat.resolve("DEP-A").id == "dep-a"
    assert cat.resolve("unknown") is None
    assert cat.dependency_chain("dep-b") == ["dep-c", "dep-b"]

    env2 = _make_env(tmp_path / "cyc")
    _write_yaml(
        env2.deps_file,
        """
        dependencies:
          - id: a
            repo: x
            depends_on: [a]
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    with pytest.raises(RuntimeError, match="cannot depend on itself"):
        DepCatalog(env2)


def test_install_dep_additional_edge_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
        """,
    )
    dep_path = env.zde_home / "dep-a"
    dep_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.configured_ref", lambda raw: ("branch", "main"))
    monkeypatch.setattr("mods.deps.wants_tag_fetch", lambda raw: False)
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: False)
    monkeypatch.setattr("mods.deps.migrate_broken_submodule_checkout", lambda *args, **kwargs: dep_path)
    monkeypatch.setattr("mods.deps.clone_repo", lambda *args, **kwargs: 0)
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_run_build_for_dep", lambda dep: 0)
    monkeypatch.setattr(cat, "_write_dep_lock_entry", lambda dep, status: None)
    monkeypatch.setattr(cat, "_write_managed_env_file", lambda: None)

    # iterdir OSError path
    original_iterdir = Path.iterdir

    def _iterdir_raises(self):
        if self == dep_path:
            raise OSError("boom")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _iterdir_raises)
    assert cat.install_dep("dep-a", include_dependencies=False) == 1


def test_update_dep_and_sync_for_update_remaining_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: req
            repo: x
            required: true
            path: home/req
          - id: opt
            repo: y
            path: home/opt
        """,
    )
    req_path = env.zde_home / "req"
    req_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.configured_ref", lambda raw: ("branch", "main"))
    monkeypatch.setattr("mods.deps.wants_tag_fetch", lambda raw: False)
    monkeypatch.setattr("mods.deps.current_commit", lambda p: "abc")
    monkeypatch.setattr("mods.deps.build_lock_entry", lambda **kwargs: {"status": kwargs["status"]})
    monkeypatch.setattr("mods.deps.write_lock", lambda p, lock: None)
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_write_dep_lock_entry", lambda dep, status: None)
    monkeypatch.setattr(cat, "_write_managed_env_file", lambda: None)

    # update_dep migrate path + iterdir OSError path + newly installed message branch
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: False)
    monkeypatch.setattr("mods.deps.migrate_broken_submodule_checkout", lambda *args, **kwargs: req_path)
    monkeypatch.setattr("mods.deps.clone_repo", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cat, "_run_build_for_dep", lambda dep: 0)
    assert cat.update_dep("req", include_dependencies=False) == 0
    assert "Installed dependency: req" in capsys.readouterr().out

    # update existing git branch and sync_failed with has_git path
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: True)
    monkeypatch.setattr("mods.deps.update_repo", lambda *args, **kwargs: 4)
    assert cat.update_dep("req", include_dependencies=False) == 4
    monkeypatch.setattr("mods.deps.update_repo", lambda *args, **kwargs: 0)
    assert cat.update_dep("req", include_dependencies=False) == 0

    # sync_for_update: has_git update path and has_git sync_fail status lock branch
    monkeypatch.setattr("mods.deps.get_skip_sync_installed_config", lambda: False)
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: True)
    monkeypatch.setattr("mods.deps.update_repo", lambda *args, **kwargs: 0)
    assert cat.sync_for_update() == 0
    monkeypatch.setattr("mods.deps.update_repo", lambda *args, **kwargs: 6)
    assert cat.sync_for_update() == 6


def test_sync_for_update_toggling_required_and_iterdir_oserror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            required: true
            path: home/dep-a
        """,
    )
    dep_path = env.zde_home / "dep-a"
    dep_path.mkdir(parents=True, exist_ok=True)
    (dep_path / "x").write_text("x", encoding="utf-8")
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.configured_ref", lambda raw: ("branch", "main"))
    monkeypatch.setattr("mods.deps.wants_tag_fetch", lambda raw: False)
    monkeypatch.setattr("mods.deps.current_commit", lambda p: "abc")
    monkeypatch.setattr("mods.deps.build_lock_entry", lambda **kwargs: {"status": kwargs["status"]})
    monkeypatch.setattr("mods.deps.write_lock", lambda p, lock: None)
    monkeypatch.setattr("mods.deps.is_git_repo", lambda p: False)
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_write_managed_env_file", lambda: None)

    # OSError during iterdir for sync_for_update line 812-813
    original_iterdir = Path.iterdir

    def _iterdir_raises(self):
        if self == dep_path:
            raise OSError("x")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _iterdir_raises)
    assert cat.sync_for_update() == 1

    # Force line 816 via toggling required property between checks
    class _ToggleRequired:
        def __init__(self):
            self.calls = 0

        def __call__(self, dep_self):
            self.calls += 1
            return self.calls == 1

    toggle = _ToggleRequired()
    monkeypatch.setattr(Dep, "required", property(toggle))
    monkeypatch.setattr(Path, "iterdir", original_iterdir)
    assert cat.sync_for_update() in {0, 1}


def test_prune_and_build_env_remaining_branches(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
        """,
    )
    dep_path = env.zde_home / "dep-a"
    dep_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: True)
    cat = DepCatalog(env)

    # prune: non-existent parent branch
    cat._prune_empty_parent_dirs(dep_path / "missing" / "child")

    # prune: rmdir OSError branch
    original_rmdir = Path.rmdir

    def _rmdir_fail(self):
        raise OSError("x")

    monkeypatch.setattr(Path, "rmdir", _rmdir_fail)
    cat._prune_empty_parent_dirs(dep_path / "child")
    monkeypatch.setattr(Path, "rmdir", original_rmdir)

    # build env empty and duplicate path branches
    monkeypatch.setenv("PATH", "")
    monkeypatch.setenv("Z88DK_PATH", "")
    monkeypatch.setenv("SDCC_PATH", "")
    monkeypatch.setenv("GNUAS_PATH", "")
    dep = cat.by_id["dep-a"]
    monkeypatch.setattr(dep, "runtime_env", lambda: [("A", "1")])
    monkeypatch.setattr(dep, "runtime_paths", lambda: ["", "/x", "/x"])
    env_out = cat._build_command_env()
    assert env_out["PATH"] == "/x"


def test_run_build_for_dep_unreachable_non_string_command_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
        """,
    )
    dep_dir = env.zde_home / "dep-a"
    dep_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: True)
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_build_command_env", lambda: os.environ.copy())

    class _WeirdList(list):
        def __init__(self):
            super().__init__(["echo ok"])
            self.phase = 0

        def __iter__(self):
            self.phase += 1
            if self.phase == 1:
                return iter(["echo ok"])
            return iter([123])

    dep = Dep(cat, {"id": "w", "repo": "x", "path": "home/dep-a", "build": {"commands": _WeirdList()}})
    assert cat._run_build_for_dep(dep) == 1


def test_dep_additional_properties_and_artifact_edge_branches(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True})
    dep_dir = catalog.env.zde_home / "dep-a"
    dep_dir.mkdir(parents=True, exist_ok=True)

    dep_categories_non_list = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "home/dep-a",
            "metadata": {"category": "not-a-list"},
            "build": False,
        },
    )
    assert dep_categories_non_list.categories == ["Other", "installed"]
    assert dep_categories_non_list.stage_disabled is True

    dep_categories_empty = Dep(
        catalog,
        {
            "id": "dep-b",
            "repo": "x",
            "path": "home/dep-a",
            "metadata": {"category": ["", " "]},
        },
    )
    assert dep_categories_empty.categories[0] == "Other"

    dep_no_metadata_dict = Dep(catalog, {"id": "dep-c", "repo": "x", "path": "home/dep-a", "metadata": 1})
    assert dep_no_metadata_dict._metadata_url_list("video") == []

    dep_no_source_dirs = Dep(catalog, {"id": "dep-d", "repo": "x", "path": "home/dep-a"})
    assert dep_no_source_dirs._infer_default_artifacts() == []

    (dep_dir / "build").mkdir(exist_ok=True)
    (dep_dir / "build" / "dirchild").mkdir(exist_ok=True)
    (dep_dir / "build" / "file.bin").write_text("x", encoding="utf-8")
    dep_infer = Dep(catalog, {"id": "dep-e", "repo": "x", "path": "home/dep-a", "build": {}})
    assert any(src.name == "file.bin" for src, _ in dep_infer.artifact_paths())

    dep_stage_disabled = Dep(catalog, {"id": "dep-f", "repo": "x", "path": "home/dep-a", "build": False})
    assert dep_stage_disabled.artifact_paths() == []

    dep_no_build = Dep(catalog, {"id": "dep-g", "repo": "x", "path": "home/dep-a"})
    dep_no_build.catalog._infer_build_tool = lambda _dep: None
    assert dep_no_build.artifact_paths() == []

    dep_bad_artifacts = Dep(catalog, {"id": "dep-h", "repo": "x", "path": "home/dep-a", "build": {"artifacts": "bad"}})
    assert dep_bad_artifacts.artifact_paths() == []

    dep_normalized_empty = Dep(
        catalog,
        {"id": "dep-i", "repo": "x", "path": "home/dep-a", "build": {"artifacts": ["/", "\\"]}},
    )
    assert dep_normalized_empty.artifact_paths() == []


def test_dep_env_items_non_string_name_branch(tmp_path: Path) -> None:
    catalog = _fake_catalog(tmp_path, installed_by_id={"dep-a": True})
    dep = Dep(
        catalog,
        {
            "id": "dep-a",
            "repo": "x",
            "path": "home/dep-a",
            "env": [{"name": 42, "path": "."}],
        },
    )
    assert dep._env_items() == []


def test_dependency_chain_runtime_cycle_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: a
            repo: x
          - id: b
            repo: y
        """,
    )
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    cat = DepCatalog(env)
    cat.by_id["a"].raw["depends_on"] = ["b"]
    cat.by_id["b"].raw["depends_on"] = ["a"]
    with pytest.raises(RuntimeError, match="Dependency cycle detected"):
        cat.dependency_chain("a")


def test_remove_dep_directory_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
        """,
    )
    dep_path = env.zde_home / "dep-a"
    dep_path.mkdir(parents=True, exist_ok=True)
    (dep_path / "file.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: True)
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_remove_dep_lock_entry", lambda dep_id: None)
    monkeypatch.setattr(cat, "refresh", lambda: None)
    assert cat.remove_dep("dep-a", force=True) == 0


def test_update_dep_iterdir_oserror_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env = _make_env(tmp_path)
    _write_yaml(
        env.deps_file,
        """
        dependencies:
          - id: dep-a
            repo: x
            path: home/dep-a
        """,
    )
    dep_path = env.zde_home / "dep-a"
    dep_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("mods.deps.load_lock", lambda _: {"dependencies": {}})
    monkeypatch.setattr("mods.deps.is_git_repo", lambda _: False)
    monkeypatch.setattr("mods.deps.migrate_broken_submodule_checkout", lambda *args, **kwargs: None)
    monkeypatch.setattr("mods.deps.configured_ref", lambda raw: ("branch", "main"))
    monkeypatch.setattr("mods.deps.wants_tag_fetch", lambda raw: False)
    cat = DepCatalog(env)
    monkeypatch.setattr(cat, "_write_dep_lock_entry", lambda dep, status: None)

    original_iterdir = Path.iterdir

    def _iterdir_raises(self):
        if self == dep_path:
            raise OSError("boom")
        return original_iterdir(self)

    monkeypatch.setattr(Path, "iterdir", _iterdir_raises)
    assert cat.update_dep("dep-a", include_dependencies=False) == 1
    monkeypatch.setattr(Path, "iterdir", original_iterdir)
