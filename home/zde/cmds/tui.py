from __future__ import annotations


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
