from __future__ import annotations

import os

from mods.config import Config
from mods.runtime import use_mode
from mods.tui.contract import ActionSpec, CommandSpec


def main(args: list[str]) -> int:
    cfg = Config.load()
    color_value, color_explicit = cfg.get_with_source("output.color")
    if color_explicit and color_value is False:
        os.environ["NO_COLOR"] = "1"

    try:
        from mods.tui.app import ZDEApp
    except ModuleNotFoundError as exc:
        missing = getattr(exc, "name", "") or ""
        if missing.startswith("textual"):
            print("The optional TUI requires Textual.")
            print("Install with: pip install textual")
            return 1
        raise

    app = ZDEApp()
    with use_mode("tui"):
        app.run()
    return 0


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="tui",
        label="tui",
        help="Launch the interactive terminal UI",
        actions=[
            ActionSpec(id="__main__", label="run", help="Open ZDE Textual interface"),
        ],
    )
