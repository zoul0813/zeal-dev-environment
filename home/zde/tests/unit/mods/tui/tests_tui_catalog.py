from __future__ import annotations

from types import ModuleType, SimpleNamespace

from mods.tui import catalog
from mods.tui.contract import ActionSpec, CommandSpec


def test_module_action_overrides_filters_invalid_entries() -> None:
    mod = ModuleType("x")
    mod.TUI_ACTION_OVERRIDES = {
        "ok": {"label": "OK"},
        "bad_key": "nope",
        1: {"label": "x"},  # type: ignore[dict-item]
    }
    overrides = catalog._module_action_overrides(mod)
    assert overrides == {"ok": {"label": "OK"}}

    mod2 = ModuleType("y")
    mod2.TUI_ACTION_OVERRIDES = "bad"
    assert catalog._module_action_overrides(mod2) == {}


def test_infer_command_spec_with_subcommands_and_overrides(monkeypatch) -> None:
    module = ModuleType("cmds.demo")
    module.TUI_ACTION_OVERRIDES = {
        "run": {"label": 123, "help": 456, "default_args": "x", "pause_after_run": 1},
        "check": {"label": "Check", "help": "Run checks", "default_args": ["-q"]},
    }
    monkeypatch.setattr(catalog, "module_name_to_command", lambda _: "demo")
    monkeypatch.setattr(catalog, "discover_subcommands", lambda _: {"check": object(), "run": object()})
    spec = catalog._infer_command_spec("cmds.demo", module)
    assert spec.name == "demo"
    assert [a.id for a in spec.actions] == ["check", "run"]
    check = spec.actions[0]
    run = spec.actions[1]
    assert check.label == "Check"
    assert check.help == "Run checks"
    assert check.default_args == ["-q"]
    assert run.label == "run"
    assert run.help == ""
    assert run.default_args == []
    assert run.pause_after_run is True


def test_infer_command_spec_without_subcommands(monkeypatch) -> None:
    monkeypatch.setattr(catalog, "module_name_to_command", lambda _: "demo")
    monkeypatch.setattr(catalog, "discover_subcommands", lambda _: {})
    spec = catalog._infer_command_spec("cmds.demo", ModuleType("cmds.demo"))
    assert spec.actions == [ActionSpec(id="__main__", label="run")]


def test_command_spec_from_module_prefers_provider(monkeypatch) -> None:
    provided = CommandSpec(name="a", label="A", actions=[ActionSpec(id="x", label="x")])
    module = ModuleType("cmds.a")
    module.get_tui_spec = lambda: provided
    assert catalog._command_spec_from_module("cmds.a", module) is provided

    module_bad = ModuleType("cmds.b")
    module_bad.get_tui_spec = lambda: "bad"
    monkeypatch.setattr(catalog, "_infer_command_spec", lambda mn, m: provided)
    assert catalog._command_spec_from_module("cmds.b", module_bad) is provided


def test_build_catalog_filters_and_sorts(monkeypatch) -> None:
    monkeypatch.setattr(catalog, "discover_command_modules", lambda: ["z", "tui", "a", "n", "empty"])
    monkeypatch.setattr(catalog, "import_command_module", lambda name: ModuleType(name))

    def _spec(module_name: str, _module: ModuleType):
        if module_name == "n":
            return None
        if module_name == "z":
            return CommandSpec(name="z", label="Zulu", actions=[ActionSpec(id="x", label="x")])
        if module_name == "a":
            return CommandSpec(name="a", label="Alpha", actions=[ActionSpec(id="y", label="y")])
        if module_name == "empty":
            return CommandSpec(name="empty", label="Empty", actions=[])
        return CommandSpec(name="x", label="X", actions=[])

    monkeypatch.setattr(catalog, "_command_spec_from_module", _spec)
    rows = catalog.build_catalog()
    assert [row.name for row in rows] == ["a", "z"]
