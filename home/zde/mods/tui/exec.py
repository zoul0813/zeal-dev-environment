from __future__ import annotations

import sys
import termios
import tty
from contextlib import contextmanager

from mods.commands import command_to_module_name, discover_subcommands, import_command_module
from mods.process import with_run_options
from mods.requirements import require_deps


@contextmanager
def suspend_for_external_output(app):
    # Hand terminal control to external commands and clear once at handoff.
    with app.suspend():
        with with_run_options(clear_before_run=True, clear_before_run_once=True):
            yield


def pause_after_run(prompt: str = "\nPress Enter or Esc to return to ZDE TUI...") -> None:
    stream = sys.stdin
    if not stream.isatty():
        try:
            input(prompt)
        except EOFError:
            pass
        return
    fd = stream.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        print(prompt, end="", flush=True)
        tty.setraw(fd)
        while True:
            ch = stream.read(1)
            if ch in ("\r", "\n", "\x1b"):
                break
    except Exception:
        try:
            input(prompt)
        except EOFError:
            pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        print("")


def run_action(command_name: str, action_id: str, args: list[str] | None = None) -> int:
    action_args = list(args or [])
    module_name = command_to_module_name(command_name)
    module = import_command_module(module_name)

    required = getattr(module, "REQUIRED_DEPS", [])
    if required and not require_deps(list(required)):
        return 1

    custom = getattr(module, "run_tui_action", None)
    if callable(custom):
        return int(custom(action_id, {"args": action_args}))

    if action_id == "__main__":
        entry = getattr(module, "main", None)
        if not callable(entry):
            print(f"Command module '{module_name}' does not define main(args)")
            return 1
        return int(entry(action_args))

    subcommands = discover_subcommands(module)
    handler = subcommands.get(action_id)
    if not callable(handler):
        print(f"Unsupported action for {command_name}: {action_id}")
        return 1
    return int(handler(action_args))
