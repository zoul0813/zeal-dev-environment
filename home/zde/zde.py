#!/usr/bin/env python3
"""ZDE in-container command router."""

from __future__ import annotations

import importlib
import sys

from common import HELP_TEXT

MODULE_ALIASES = {
    "-i": "shell",
    "emu": "emulator",
}

def print_top_help() -> int:
    print(HELP_TEXT)
    return 0

def main(argv: list[str]) -> int:
    if not argv or argv[0] == "help":
        return print_top_help()

    module_name = MODULE_ALIASES.get(argv[0], argv[0]).replace("-", "_")
    module_args = argv[1:]

    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            print(f"Unknown command module: {module_name}")
            return print_top_help()
        raise

    entry = getattr(module, "main", None)
    if entry is None:
        print(f"Command module '{module_name}' does not define main(args)")
        return 1

    return int(entry(module_args))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
