from __future__ import annotations

from types import SimpleNamespace

import pytest

import zde as zde_router


def test_main_prints_top_help_when_no_args(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(zde_router, "discover_command_modules", lambda: ["config", "deps"])
    rc = zde_router.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Commands:" in out
    assert "config, deps" in out


def test_main_handles_host_service_alias(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    rc = zde_router.main(["emu"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "'emulator' is a host-only service command." in out
    assert "Run it from the host wrapper: ./zde emulator" in out


def test_main_unknown_module_falls_back_to_top_help(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(zde_router, "discover_command_modules", lambda: ["deps"])

    def _raise(module_name: str):
        raise ModuleNotFoundError("missing", name=f"cmds.{module_name}")

    monkeypatch.setattr(zde_router, "import_command_module", _raise)
    rc = zde_router.main(["unknown"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Unknown command module: unknown" in out
    assert "Commands:" in out


def test_main_routes_legacy_romdisk_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, list[str]] = {}

    def _main(args: list[str]) -> int:
        calls["args"] = args
        return 0

    monkeypatch.setattr(zde_router, "import_command_module", lambda module_name: SimpleNamespace(main=_main))
    monkeypatch.setattr(zde_router, "discover_subcommands", lambda module: {})
    rc = zde_router.main(["romdisk", "ls"])
    assert rc == 0
    assert calls["args"] == ["romdisk", "ls"]


def test_main_dispatches_subcommand_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zde_router, "import_command_module", lambda module_name: SimpleNamespace(main=lambda args: 99))
    monkeypatch.setattr(zde_router, "discover_subcommands", lambda module: {"list": lambda args: 7})
    rc = zde_router.main(["deps", "list", "games"])
    assert rc == 7


def test_main_honors_required_deps_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    module = SimpleNamespace(main=lambda args: 0, REQUIRED_DEPS=["dep-a"])
    monkeypatch.setattr(zde_router, "import_command_module", lambda module_name: module)
    monkeypatch.setattr(zde_router, "discover_subcommands", lambda module: {})
    monkeypatch.setattr(zde_router, "require_deps", lambda dep_ids: False)
    rc = zde_router.main(["kernel"])
    assert rc == 1
