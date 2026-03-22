from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest


def test_run_tui_action_routes_to_run_kernel(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    cmd_kernel = importlib.import_module("cmds.kernel")

    seen: list[list[str]] = []

    def _run_kernel(args: list[str]) -> int:
        seen.append(args)
        return 42 if args and args[0] == "x" else 0

    monkeypatch.setattr(cmd_kernel, "run_kernel", _run_kernel)

    assert cmd_kernel.run_tui_action("__main__", {"args": ["x"]}) == 42
    assert cmd_kernel.run_tui_action("user", {"args": []}) == 0
    assert cmd_kernel.run_tui_action("menuconfig", {"args": []}) == 0
    assert cmd_kernel.run_tui_action("default", {"args": []}) == 0
    assert cmd_kernel.run_tui_action("config:abc", {"args": ["--fast"]}) == 0
    assert cmd_kernel.run_tui_action("dep:dep-a", {"args": ["--x"]}) == 0

    assert seen[0] == ["x"]
    assert ["user"] in seen
    assert ["menuconfig"] in seen
    assert ["default"] in seen
    assert ["abc", "--fast"] in seen
    assert ["dep-a", "--x"] in seen

    assert cmd_kernel.run_tui_action("config:", {"args": []}) == 1
    assert "Invalid kernel config action." in capsys.readouterr().out
    assert cmd_kernel.run_tui_action("dep:", {"args": []}) == 1
    assert "Invalid dep kernel config action." in capsys.readouterr().out
    assert cmd_kernel.run_tui_action("other", {"args": []}) == 0
    assert ["other"] in seen


def test_get_tui_spec_orders_special_then_kernel_then_dep(monkeypatch: pytest.MonkeyPatch) -> None:
    cmd_kernel = importlib.import_module("cmds.kernel")

    monkeypatch.setattr(
        cmd_kernel,
        "list_kernel_options",
        lambda: [
            SimpleNamespace(action_id="config:agon", label="agon", help="Build (Agon)", args=["agon"]),
            SimpleNamespace(action_id="config:zeal8bit", label="zeal8bit", help="Build (Zeal)", args=["zeal8bit"]),
            SimpleNamespace(action_id="dep:zshell", label="zshell", help="Build (ZShell)", args=["zshell"]),
        ],
    )

    spec = cmd_kernel.get_tui_spec()
    assert [action.id for action in spec.actions] == [
        "user",
        "menuconfig",
        "default",
        "config:agon",
        "config:zeal8bit",
        "dep:zshell",
    ]
