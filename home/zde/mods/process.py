from __future__ import annotations

import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from mods.runtime import is_tui_mode


@dataclass
class _RunOptions:
    clear_before_run: bool | None = None
    clear_before_run_once: bool = False
    pause_on_error: bool | None = None
    pause_message: str = "Command failed. Press Enter to continue..."
    _cleared: bool = False


_RUN_OPTIONS_STACK: list[_RunOptions] = [_RunOptions()]


def _current_options() -> _RunOptions:
    return _RUN_OPTIONS_STACK[-1]


@contextmanager
def with_run_options(
    *,
    clear_before_run: bool | None = None,
    clear_before_run_once: bool | None = None,
    pause_on_error: bool | None = None,
    pause_message: str | None = None,
) -> Iterator[None]:
    current = _current_options()
    merged = _RunOptions(
        clear_before_run=current.clear_before_run if clear_before_run is None else clear_before_run,
        clear_before_run_once=current.clear_before_run_once if clear_before_run_once is None else clear_before_run_once,
        pause_on_error=current.pause_on_error if pause_on_error is None else pause_on_error,
        pause_message=current.pause_message if pause_message is None else pause_message,
    )
    _RUN_OPTIONS_STACK.append(merged)
    try:
        yield
    finally:
        _RUN_OPTIONS_STACK.pop()


def _apply_pre_run_behavior(stdout: object | None, capture_output: bool) -> None:
    opts = _current_options()
    clear_before_run = opts.clear_before_run
    if clear_before_run is None:
        clear_before_run = is_tui_mode()
    if not clear_before_run:
        return
    if capture_output:
        return
    if stdout is not None:
        return
    if opts.clear_before_run_once and opts._cleared:
        return
    if not sys.stdout.isatty():
        return
    sys.stdout.write("\x1b[2J\x1b[H")
    sys.stdout.flush()
    opts._cleared = True


def _should_pause_on_error(stdout: object | None, capture_output: bool) -> bool:
    opts = _current_options()
    pause_on_error = opts.pause_on_error
    if pause_on_error is None:
        pause_on_error = is_tui_mode()
    if not pause_on_error:
        return False
    if capture_output:
        return False
    if stdout is not None:
        return False
    if not (sys.stdin.isatty() and sys.stdout.isatty()):
        return False
    return True


def _pause_after_error() -> None:
    message = _current_options().pause_message
    try:
        input(f"\n{message}")
    except EOFError:
        pass


def run(
    cmd: list[str],
    cwd: Path | None = None,
    *,
    env: dict[str, str] | None = None,
    stdout: object | None = None,
    stderr: object | None = None,
    input_text: str | None = None,
) -> int:
    _apply_pre_run_behavior(stdout=stdout, capture_output=False)
    text_mode = input_text is not None
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            check=False,
            env=env,
            stdout=stdout,
            stderr=stderr,
            input=input_text,
            text=text_mode,
        )
        if result.returncode != 0 and _should_pause_on_error(stdout=stdout, capture_output=False):
            _pause_after_error()
        return result.returncode
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}")
        if _should_pause_on_error(stdout=stdout, capture_output=False):
            _pause_after_error()
        return 127


def run_checked(
    cmd: list[str],
    cwd: Path | None = None,
    *,
    env: dict[str, str] | None = None,
    stdout: object | None = None,
    stderr: object | None = None,
    input_text: str | None = None,
) -> None:
    _apply_pre_run_behavior(stdout=stdout, capture_output=False)
    text_mode = input_text is not None
    subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        env=env,
        stdout=stdout,
        stderr=stderr,
        input=input_text,
        text=text_mode,
    )


def run_capture(
    cmd: list[str],
    cwd: Path | None = None,
    *,
    env: dict[str, str] | None = None,
    input_text: str | None = None,
) -> str:
    # Captured runs don't render to terminal, so no terminal pre-run behavior.
    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        env=env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.strip()
