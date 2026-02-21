from __future__ import annotations

from typing import Any

from mods.config import load_config, save_config


def load_tui_preferences() -> dict[str, Any]:
    config = load_config()
    tui = config.get("tui", {})
    if not isinstance(tui, dict):
        return {}
    textual = tui.get("textual", {})
    if not isinstance(textual, dict):
        return {}
    return textual


def save_tui_preferences(theme: str | None, dark: bool) -> None:
    config = load_config()
    if not isinstance(config, dict):
        config = {}
    tui = config.setdefault("tui", {})
    if not isinstance(tui, dict):
        tui = {}
        config["tui"] = tui
    textual = tui.setdefault("textual", {})
    if not isinstance(textual, dict):
        textual = {}
        tui["textual"] = textual

    if isinstance(theme, str) and theme:
        textual["theme"] = theme
    else:
        textual.pop("theme", None)
    textual["dark"] = bool(dark)

    save_config(config)

