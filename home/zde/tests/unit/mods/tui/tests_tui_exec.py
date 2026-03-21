from __future__ import annotations

from contextlib import contextmanager
from types import ModuleType, SimpleNamespace

import pytest

from mods.tui import exec as tui_exec


def test_suspend_for_external_output_uses_suspend_and_run_options(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []

    @contextmanager
    def _ctx(tag: str):
        events.append(f"{tag}:enter")
        try:
            yield
        finally:
            events.append(f"{tag}:exit")

    class _App:
        def suspend(self):
            return _ctx("suspend")

    monkeypatch.setattr(tui_exec, "with_run_options", lambda **kwargs: _ctx("options"))
    with tui_exec.suspend_for_external_output(_App()):
        events.append("body")
    assert events == [
        "suspend:enter",
        "options:enter",
        "body",
        "options:exit",
        "suspend:exit",
    ]


class _FakeStdin:
    def __init__(self, tty: bool, chars: str = "\n") -> None:
        self._tty = tty
        self._chars = list(chars)

    def isatty(self) -> bool:
        return self._tty

    def fileno(self) -> int:
        return 1

    def read(self, _n: int) -> str:
        return self._chars.pop(0) if self._chars else "\n"


def test_pause_after_run_non_tty_and_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tui_exec.sys, "stdin", _FakeStdin(False))
    calls: list[str] = []
    monkeypatch.setattr("builtins.input", lambda prompt: calls.append(prompt) or "")
    tui_exec.pause_after_run("P>")
    assert calls == ["P>"]

    def _raise(_prompt: str) -> str:
        raise EOFError()

    monkeypatch.setattr("builtins.input", _raise)
    tui_exec.pause_after_run("P>")


def test_pause_after_run_tty_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tui_exec.sys, "stdin", _FakeStdin(True, chars="x\x1b"))
    monkeypatch.setattr(tui_exec.termios, "tcgetattr", lambda _fd: ("old",))
    set_calls: list[str] = []
    monkeypatch.setattr(tui_exec.termios, "tcsetattr", lambda _fd, _mode, _old: set_calls.append("set"))
    monkeypatch.setattr(tui_exec.tty, "setraw", lambda _fd: None)
    tui_exec.pause_after_run("P>")
    assert set_calls == ["set"]

    # Exception path falls back to input().
    monkeypatch.setattr(tui_exec.sys, "stdin", _FakeStdin(True, chars=""))
    monkeypatch.setattr(tui_exec.tty, "setraw", lambda _fd: (_ for _ in ()).throw(RuntimeError("x")))
    prompts: list[str] = []
    monkeypatch.setattr("builtins.input", lambda prompt: prompts.append(prompt) or "")
    tui_exec.pause_after_run("Q>")
    assert prompts == ["Q>"]

    def _raise_eof(_prompt: str) -> str:
        raise EOFError()

    monkeypatch.setattr("builtins.input", _raise_eof)
    tui_exec.pause_after_run("Q>")


def test_run_action_dispatch(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(tui_exec, "command_to_module_name", lambda name: f"cmds.{name}")
    monkeypatch.setattr(tui_exec, "discover_subcommands", lambda _m: {"sub": lambda args: 7})

    module = ModuleType("cmds.demo")
    module.REQUIRED_DEPS = ["A"]
    monkeypatch.setattr(tui_exec, "import_command_module", lambda _mn: module)
    monkeypatch.setattr(tui_exec, "require_deps", lambda deps: False)
    assert tui_exec.run_action("demo", "__main__") == 1

    monkeypatch.setattr(tui_exec, "require_deps", lambda deps: True)
    module.run_tui_action = lambda action_id, context: 9
    assert tui_exec.run_action("demo", "x", ["a"]) == 9
    del module.run_tui_action

    assert tui_exec.run_action("demo", "__main__", ["a"]) == 1
    assert "does not define main(args)" in capsys.readouterr().out

    module.main = lambda args: 3
    assert tui_exec.run_action("demo", "__main__", ["a"]) == 3

    monkeypatch.setattr(tui_exec, "discover_subcommands", lambda _m: {})
    assert tui_exec.run_action("demo", "missing", ["a"]) == 1
    assert "Unsupported action for demo: missing" in capsys.readouterr().out

    monkeypatch.setattr(tui_exec, "discover_subcommands", lambda _m: {"ok": lambda args: 11})
    assert tui_exec.run_action("demo", "ok", ["a"]) == 11
