from __future__ import annotations

import pkgutil
from types import SimpleNamespace

from mods import commands


def test_module_command_name_normalization() -> None:
    assert commands.module_name_to_command("foo_bar") == "foo-bar"
    assert commands.command_to_module_name("foo-bar") == "foo_bar"


def test_build_alias_lookup_normalizes_alias_tokens() -> None:
    lookup = commands.build_alias_lookup({"deps": ["d", "dep-tools"]})
    assert lookup["d"] == "deps"
    assert lookup["dep_tools"] == "deps"


def test_discover_subcommands_only_returns_callable_subcmd_prefixed_attrs() -> None:
    module = SimpleNamespace(
        subcmd_list=lambda args: 0,
        subcmd_install=lambda args: 1,
        subcmd_invalid="not-callable",
        something_else=lambda args: 0,
    )
    subcommands = commands.discover_subcommands(module)  # type: ignore[arg-type]
    assert sorted(subcommands.keys()) == ["install", "list"]


def test_discover_command_modules_filters_private_and_sorts(monkeypatch) -> None:
    fake_modules = [
        pkgutil.ModuleInfo(module_finder=None, name="zeta", ispkg=False),
        pkgutil.ModuleInfo(module_finder=None, name="_private", ispkg=False),
        pkgutil.ModuleInfo(module_finder=None, name="alpha", ispkg=False),
    ]
    monkeypatch.setattr(commands.pkgutil, "iter_modules", lambda path: fake_modules)
    monkeypatch.setattr(commands.cmds, "__path__", ["/tmp/fake-cmds"])
    assert commands.discover_command_modules() == ["alpha", "zeta"]


def test_import_command_module_uses_cmds_prefix(monkeypatch) -> None:
    calls: list[str] = []

    def _import(name: str):
        calls.append(name)
        return SimpleNamespace(name=name)

    monkeypatch.setattr(commands.importlib, "import_module", _import)
    module = commands.import_command_module("deps")
    assert module.name == "cmds.deps"
    assert calls == ["cmds.deps"]
