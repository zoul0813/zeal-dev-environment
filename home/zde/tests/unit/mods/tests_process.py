from __future__ import annotations

from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from mods import process
from helpers.mocks import FakeTty


@pytest.fixture(autouse=True)
def _reset_run_options_stack() -> None:
    process._RUN_OPTIONS_STACK[:] = [process._RunOptions()]


def test_run_returns_subprocess_returncode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=3))
    assert process.run(["echo", "x"]) == 3


def test_run_returns_127_when_command_missing(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def _raise(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "missing-cmd")

    monkeypatch.setattr(subprocess, "run", _raise)
    rc = process.run(["missing-cmd"])
    out = capsys.readouterr().out
    assert rc == 127
    assert "Command not found: missing-cmd" in out


def test_run_checked_raises_runtimeerror_when_command_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "missing-cmd")

    monkeypatch.setattr(subprocess, "run", _raise)
    with pytest.raises(RuntimeError, match="Command not found: missing-cmd"):
        process.run_checked(["missing-cmd"])


def test_run_capture_raises_runtimeerror_when_command_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "missing-cmd")

    monkeypatch.setattr(subprocess, "run", _raise)
    with pytest.raises(RuntimeError, match="Command not found: missing-cmd"):
        process.run_capture(["missing-cmd"])


def test_with_run_options_apply_and_pop() -> None:
    base = process._current_options()
    assert base.pause_message == "Command failed. Press Enter to continue..."
    with process.with_run_options(clear_before_run=True, clear_before_run_once=True, pause_on_error=True, pause_message="Hold"):
        cur = process._current_options()
        assert cur.clear_before_run is True
        assert cur.clear_before_run_once is True
        assert cur.pause_on_error is True
        assert cur.pause_message == "Hold"
    restored = process._current_options()
    assert restored.pause_message == base.pause_message


def test_apply_pre_run_behavior_branches(monkeypatch: pytest.MonkeyPatch) -> None:
    out_tty = FakeTty(tty=True)
    monkeypatch.setattr(process.sys, "stdout", out_tty)
    monkeypatch.setattr(process, "is_tui_mode", lambda: True)

    # Clears when in TUI, not capturing, no custom stdout.
    process._apply_pre_run_behavior(stdout=None, capture_output=False)
    assert out_tty.writes
    assert process._current_options()._cleared is True

    # clear_before_run_once short-circuit when already cleared.
    with process.with_run_options(clear_before_run=True, clear_before_run_once=True):
        process._current_options()._cleared = True
        out_tty.writes.clear()
        process._apply_pre_run_behavior(stdout=None, capture_output=False)
        assert out_tty.writes == []

    # Capture and explicit stdout short-circuit.
    out_tty.writes.clear()
    process._apply_pre_run_behavior(stdout=None, capture_output=True)
    process._apply_pre_run_behavior(stdout=object(), capture_output=False)
    assert out_tty.writes == []

    # Non-tty short-circuit.
    out_notty = FakeTty(tty=False)
    monkeypatch.setattr(process.sys, "stdout", out_notty)
    process._apply_pre_run_behavior(stdout=None, capture_output=False)
    assert out_notty.writes == []


def test_should_pause_on_error_and_pause_after_error(monkeypatch: pytest.MonkeyPatch) -> None:
    stdin_tty = FakeTty(tty=True)
    stdout_tty = FakeTty(tty=True)
    monkeypatch.setattr(process.sys, "stdin", stdin_tty)
    monkeypatch.setattr(process.sys, "stdout", stdout_tty)
    monkeypatch.setattr(process, "is_tui_mode", lambda: True)

    assert process._should_pause_on_error(stdout=None, capture_output=False) is True
    assert process._should_pause_on_error(stdout=None, capture_output=True) is False
    assert process._should_pause_on_error(stdout=object(), capture_output=False) is False

    stdout_notty = FakeTty(tty=False)
    monkeypatch.setattr(process.sys, "stdout", stdout_notty)
    assert process._should_pause_on_error(stdout=None, capture_output=False) is False

    captured: list[str] = []
    monkeypatch.setattr("builtins.input", lambda msg: captured.append(msg) or "")
    with process.with_run_options(pause_message="Paused"):
        process._pause_after_error()
    assert captured == ["\nPaused"]

    def _raise_eof(_msg: str) -> str:
        raise EOFError()

    monkeypatch.setattr("builtins.input", _raise_eof)
    process._pause_after_error()


def test_run_pause_and_parameter_passthrough(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    seen: dict[str, object] = {}
    paused = {"count": 0}

    def _run(*args, **kwargs):
        seen.update(kwargs)
        return SimpleNamespace(returncode=4)

    monkeypatch.setattr(subprocess, "run", _run)
    monkeypatch.setattr(process, "_should_pause_on_error", lambda **kwargs: True)
    monkeypatch.setattr(process, "_pause_after_error", lambda: paused.__setitem__("count", paused["count"] + 1))
    rc = process.run(
        ["cmd"],
        cwd=tmp_path,
        env={"A": "1"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        input_text="in",
    )
    assert rc == 4
    assert paused["count"] == 1
    assert seen["cwd"] == str(tmp_path)
    assert seen["env"] == {"A": "1"}
    assert seen["text"] is True
    assert seen["input"] == "in"

    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: SimpleNamespace(returncode=0))
    assert process.run(["cmd"], input_text=None) == 0


def test_run_missing_command_pause_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "missing-cmd")

    paused = {"count": 0}
    monkeypatch.setattr(subprocess, "run", _raise)
    monkeypatch.setattr(process, "_should_pause_on_error", lambda **kwargs: True)
    monkeypatch.setattr(process, "_pause_after_error", lambda: paused.__setitem__("count", paused["count"] + 1))
    assert process.run(["missing-cmd"]) == 127
    assert paused["count"] == 1


def test_run_checked_and_capture_success_paths(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    calls: list[dict[str, object]] = []

    def _run(*args, **kwargs):
        calls.append(kwargs)
        if kwargs.get("stdout") is subprocess.PIPE:
            return SimpleNamespace(stdout="  hello \n")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(subprocess, "run", _run)
    process.run_checked(["cmd"], cwd=tmp_path, env={"A": "1"}, input_text="x")
    assert calls[0]["cwd"] == str(tmp_path)
    assert calls[0]["check"] is True
    assert calls[0]["text"] is True
    assert calls[0]["input"] == "x"

    out = process.run_capture(["cmd"], cwd=tmp_path, env={"A": "1"}, input_text="x")
    assert out == "hello"
