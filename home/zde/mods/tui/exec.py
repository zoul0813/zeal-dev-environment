from __future__ import annotations

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


def run_action(command_name: str, action_id: str, args: list[str] | None = None) -> int:
    action_args = list(args or [])
    module_name = command_to_module_name(command_name, {"emulator": ["emu"]})
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
