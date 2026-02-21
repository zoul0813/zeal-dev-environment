from __future__ import annotations

from mods.tui.contract import ActionSpec, CommandSpec


def main(args: list[str]) -> int:
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
