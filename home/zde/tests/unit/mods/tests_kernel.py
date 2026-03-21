from __future__ import annotations

import builtins
from pathlib import Path
import subprocess
import sys
from types import ModuleType, SimpleNamespace

import pytest

from mods import kernel


def test_dep_kernel_config_from_lock_branches(tmp_path: Path) -> None:
    dep_root = tmp_path / "dep"
    dep_root.mkdir(parents=True, exist_ok=True)
    conf = dep_root / "os.conf"
    conf.write_text("CONFIG=1\n", encoding="utf-8")

    assert kernel._dep_kernel_config_from_lock("dep", None) is None
    assert kernel._dep_kernel_config_from_lock("dep", {"path": ""}) is None
    assert kernel._dep_kernel_config_from_lock("dep", {"path": str(dep_root)}) is None
    assert kernel._dep_kernel_config_from_lock("dep", {"path": str(dep_root), "kernel_config": {"path": ""}}) is None
    assert kernel._dep_kernel_config_from_lock("dep", {"path": str(dep_root), "kernel_config": {"path": "missing.conf"}}) is None

    cfg = kernel._dep_kernel_config_from_lock(
        "dep",
        {
            "path": str(dep_root),
            "kernel_config": {"path": "os.conf", "aliases": [1, " alias ", ""]},
        },
    )
    assert cfg is not None
    assert cfg.aliases == [" alias "]
    assert cfg.os_conf == conf

    cfg_default_aliases = kernel._dep_kernel_config_from_lock(
        "dep",
        {"path": str(dep_root), "kernel_config": {"path": "os.conf", "aliases": []}},
        ["dep", "", 42, "alt"],  # type: ignore[list-item]
    )
    assert cfg_default_aliases is not None
    assert cfg_default_aliases.aliases == ["dep", "alt"]


def test_list_kernel_configs_and_options(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    zos = tmp_path / "zos"
    (zos / "configs").mkdir(parents=True, exist_ok=True)
    (zos / "configs" / "zeal8bit.default").write_text("x", encoding="utf-8")
    (zos / "configs" / "user.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(kernel, "ZOS_PATH", zos)

    assert kernel.list_kernel_configs() == ["zeal8bit"]

    monkeypatch.setattr(
        kernel,
        "list_dep_kernel_configs",
        lambda: [kernel.DepKernelConfig(dep_id="dep-a", aliases=["a1", "a2"], os_conf=tmp_path / "a.conf")],
    )
    options = kernel.list_kernel_options()
    assert any(opt.action_id == "config:zeal8bit" for opt in options)
    dep_opt = next(opt for opt in options if opt.action_id == "dep:dep-a")
    assert dep_opt.label == "a1"
    assert "aliases: a1, a2" in dep_opt.help
    assert options[-1].action_id == "user"

    monkeypatch.setattr(kernel, "ZOS_PATH", tmp_path / "missing-zos")
    assert kernel.list_kernel_configs() == []


def test_list_dep_kernel_configs_import_and_sorting_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    original_import = builtins.__import__

    def _import_fail(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mods.deps":
            raise RuntimeError("boom")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import_fail)
    assert kernel.list_dep_kernel_configs() == []
    monkeypatch.setattr(builtins, "__import__", original_import)

    dep_root = tmp_path / "dep-root"
    dep_root.mkdir(parents=True, exist_ok=True)
    conf = dep_root / "os.conf"
    conf.write_text("x", encoding="utf-8")

    class _Dep:
        def __init__(self, dep_id: str, aliases: list[str]) -> None:
            self.id = dep_id
            self.aliases = aliases

    class _Catalog:
        def __init__(self) -> None:
            self.lock_deps = {
                "Zeta": {"path": str(dep_root), "kernel_config": {"path": "os.conf"}},
                "alpha": {"path": str(dep_root), "kernel_config": {"path": "os.conf", "aliases": ["a"]}},
                "skip": {"path": str(dep_root)},
            }

        def installed(self):
            return [_Dep("Zeta", ["z"]), _Dep("skip", []), _Dep("alpha", ["a"])]

    fake_mod = ModuleType("mods.deps")
    fake_mod.DepCatalog = _Catalog  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mods.deps", fake_mod)
    rows = kernel.list_dep_kernel_configs()
    assert [row.dep_id for row in rows] == ["alpha", "Zeta"]


def test_resolve_dep_kernel_config_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    original_import = builtins.__import__

    def _import_fail(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mods.deps":
            raise RuntimeError("boom")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _import_fail)
    assert kernel._resolve_dep_kernel_config("dep") is None
    monkeypatch.setattr(builtins, "__import__", original_import)

    dep_root = tmp_path / "dep-root"
    dep_root.mkdir(parents=True, exist_ok=True)
    conf = dep_root / "os.conf"
    conf.write_text("x", encoding="utf-8")

    class _Dep:
        def __init__(self, dep_id: str, installed: bool, aliases: list[str]) -> None:
            self.id = dep_id
            self.installed = installed
            self.aliases = aliases

    class _Catalog:
        def __init__(self, dep_obj, resolve_error: bool = False) -> None:
            self.dep_obj = dep_obj
            self.resolve_error = resolve_error
            self.lock_deps = {"dep": {"path": str(dep_root), "kernel_config": {"path": "os.conf"}}}

        def resolve(self, raw_id: str):
            if self.resolve_error:
                raise RuntimeError("bad")
            return self.dep_obj

    fake_mod = ModuleType("mods.deps")
    fake_mod.DepCatalog = lambda: _Catalog(None)  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "mods.deps", fake_mod)
    assert kernel._resolve_dep_kernel_config("   ") is None
    assert kernel._resolve_dep_kernel_config("dep") is None

    fake_mod.DepCatalog = lambda: _Catalog(_Dep("dep", False, []))  # type: ignore[attr-defined]
    assert kernel._resolve_dep_kernel_config("dep") is None

    fake_mod.DepCatalog = lambda: _Catalog(_Dep("dep", True, ["a"]))  # type: ignore[attr-defined]
    cfg = kernel._resolve_dep_kernel_config("dep")
    assert cfg is not None
    assert cfg.dep_id == "dep"

    fake_mod.DepCatalog = lambda: _Catalog(_Dep("dep", True, []), resolve_error=True)  # type: ignore[attr-defined]
    assert kernel._resolve_dep_kernel_config("dep") is None


def test_kernel_version_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    zos = tmp_path / "zos"
    zos.mkdir(parents=True, exist_ok=True)

    calls = {"n": 0}

    def _run_success(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return SimpleNamespace(stdout="v1.2.3\n")
        raise AssertionError("unexpected")

    monkeypatch.setattr(kernel.subprocess, "run", _run_success)
    assert kernel._kernel_version(zos) == "v1.2.3"

    def _run_sha_only(*args, **kwargs):
        cmd = args[0]
        if cmd[3] == "describe":
            return SimpleNamespace(stdout="abcdef1\n")
        if cmd[3] == "for-each-ref":
            return SimpleNamespace(stdout="v9.0.0\nv8.0.0\n")
        if cmd[3] == "rev-parse":
            return SimpleNamespace(stdout="deadbee\n")
        raise AssertionError("unexpected")

    monkeypatch.setattr(kernel.subprocess, "run", _run_sha_only)
    assert kernel._kernel_version(zos) == "v9.0.0-deadbee"

    def _run_points_at(*args, **kwargs):
        cmd = args[0]
        if cmd[3] == "describe":
            raise subprocess.CalledProcessError(1, cmd, stderr="d")
        if cmd[3] == "for-each-ref":
            raise subprocess.CalledProcessError(1, cmd, stderr="f")
        if cmd[3] == "tag":
            return SimpleNamespace(stdout="v1.0.0\nv2.0.0\n")
        raise AssertionError("unexpected")

    monkeypatch.setattr(kernel.subprocess, "run", _run_points_at)
    assert kernel._kernel_version(zos) == "v2.0.0"

    def _run_fallback_sha(*args, **kwargs):
        cmd = args[0]
        if cmd[3] == "describe":
            raise subprocess.CalledProcessError(1, cmd, stderr="d")
        if cmd[3] == "for-each-ref":
            raise subprocess.CalledProcessError(1, cmd, stderr="f")
        if cmd[3] == "tag":
            raise subprocess.CalledProcessError(1, cmd, stderr="t")
        if cmd[3] == "rev-parse":
            return SimpleNamespace(stdout="cafebad\n")
        raise AssertionError("unexpected")

    monkeypatch.setattr(kernel.subprocess, "run", _run_fallback_sha)
    assert kernel._kernel_version(zos) == "cafebad"

    def _run_latest_tag_only(*args, **kwargs):
        cmd = args[0]
        if cmd[3] == "describe":
            raise subprocess.CalledProcessError(1, cmd, stderr="d")
        if cmd[3] == "for-each-ref":
            return SimpleNamespace(stdout="v3.1.4\n")
        if cmd[3] == "rev-parse":
            raise subprocess.CalledProcessError(1, cmd, stderr="rp")
        raise AssertionError("unexpected")

    monkeypatch.setattr(kernel.subprocess, "run", _run_latest_tag_only)
    assert kernel._kernel_version(zos) == "v3.1.4"

    def _run_unversioned_via_calledprocesserror(*args, **kwargs):
        cmd = args[0]
        if cmd[3] == "describe":
            raise subprocess.CalledProcessError(1, cmd, stderr="d")
        if cmd[3] == "for-each-ref":
            raise subprocess.CalledProcessError(1, cmd, stderr="f")
        if cmd[3] == "tag":
            raise subprocess.CalledProcessError(1, cmd, stderr="t")
        if cmd[3] == "rev-parse":
            raise subprocess.CalledProcessError(1, cmd, stderr="rp")
        raise AssertionError("unexpected")

    monkeypatch.setattr(kernel.subprocess, "run", _run_unversioned_via_calledprocesserror)
    assert kernel._kernel_version(zos) == "unversioned"

    def _run_fail(*args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(kernel.subprocess, "run", _run_fail)
    assert kernel._kernel_version(zos) == "unversioned"
    out = capsys.readouterr().out
    assert "Warning: kernel version detection failed" in out


def test_build_kernel_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    zos = tmp_path / "zos"
    build_dir = zos / "build"
    build_dir.mkdir(parents=True, exist_ok=True)
    fullbin = build_dir / "os_with_romdisk.img"
    mnt = tmp_path / "mnt"
    monkeypatch.setattr(kernel, "ZOS_PATH", zos)
    monkeypatch.setattr(kernel, "MNT_DIR", mnt)
    monkeypatch.setattr(kernel, "_kernel_version", lambda _: "v1")

    calls: list[list[str]] = []

    def _run_ok(cmd, **kwargs):
        calls.append(cmd)
        return 0

    monkeypatch.setattr(kernel, "run", _run_ok)
    assert kernel.build_kernel("user") == 1
    assert "missing image" in capsys.readouterr().out

    fullbin.write_bytes(b"")
    assert kernel.build_kernel("zeal8bit") == 1
    assert "has size 0" in capsys.readouterr().out

    fullbin.write_bytes(b"abc")
    latest = mnt / "roms" / "latest.img"
    latest.parent.mkdir(parents=True, exist_ok=True)
    latest.write_text("old", encoding="utf-8")
    assert kernel.build_kernel("zeal8bit") == 0
    out = capsys.readouterr().out
    assert "Copied to" in out
    assert latest.is_symlink()

    os_conf = zos / "os.conf"
    os_conf.write_text("x", encoding="utf-8")
    assert kernel.build_kernel("default") == 0
    assert not os_conf.exists()
    assert kernel.build_kernel("menuconfig") == 0
    assert kernel.build_kernel("custom") == 0

    def _run_fail_config(cmd, **kwargs):
        return 9 if cmd[:2] == ["cmake", "-B"] else 0

    monkeypatch.setattr(kernel, "run", _run_fail_config)
    assert kernel.build_kernel("user") == 9

    def _run_fail_build(cmd, **kwargs):
        return 8 if cmd[:2] == ["cmake", "--build"] else 0

    monkeypatch.setattr(kernel, "run", _run_fail_build)
    assert kernel.build_kernel("user") == 8


def test_run_kernel_branches(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys) -> None:
    zos = tmp_path / "zos"
    user = tmp_path / "user"
    zos.mkdir(parents=True, exist_ok=True)
    user.mkdir(parents=True, exist_ok=True)
    os_conf = zos / "os.conf"
    user_conf = user / "os.conf"
    monkeypatch.setattr(kernel, "ZOS_PATH", zos)
    monkeypatch.setattr(kernel, "USER_STATE_DIR", user)
    monkeypatch.setattr(kernel, "list_kernel_configs", lambda: ["zeal8bit"])
    monkeypatch.setattr(kernel, "_resolve_dep_kernel_config", lambda _: None)
    monkeypatch.setattr(kernel, "build_kernel", lambda _: 0)

    assert kernel.run_kernel(["unknown"]) == 1
    assert "Unknown kernel config: unknown" in capsys.readouterr().out

    user_conf.write_text("U\n", encoding="utf-8")
    assert kernel.run_kernel(["user"]) == 0
    assert os_conf.read_text(encoding="utf-8") == "U\n"

    user_conf.unlink()
    os_conf.write_text("M\n", encoding="utf-8")
    assert kernel.run_kernel(["menuconfig"]) == 0
    assert user_conf.read_text(encoding="utf-8") == "M\n"

    dep_conf = tmp_path / "dep.conf"
    dep_conf.write_text("D\n", encoding="utf-8")
    monkeypatch.setattr(
        kernel,
        "_resolve_dep_kernel_config",
        lambda _: kernel.DepKernelConfig(dep_id="dep-a", aliases=[], os_conf=dep_conf),
    )
    assert kernel.run_kernel(["dep-a"]) == 0
    assert os_conf.read_text(encoding="utf-8") == "D\n"
