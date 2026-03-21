from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
from typing import Any

from textual.app import App
from textual.screen import Screen
from textual.widgets import Static

from mods.config import Config
from mods.tui.catalog import build_catalog
from mods.tui.panels.command_menu import CommandMenuScreen


class ZDEApp(App[None]):
    TITLE = "Zeal Dev Environment"
    SUB_TITLE = "Terminal UI"
    CSS_PATH = "style.tcss"

    def on_mount(self) -> None:
        cfg = Config.load()
        theme = cfg.get("textual.theme")
        if not isinstance(theme, str) or not theme:
            theme = "monokai"
        if isinstance(theme, str) and theme:
            try:
                self.theme = theme
            except Exception:
                pass
        commands = build_catalog()
        self.push_screen(CommandMenuScreen(commands))
        self._refresh_cwd_bar()
        self.set_interval(1.0, self._refresh_cwd_bar)

    def _persist_theme_preference(self) -> None:
        cfg = Config.load()
        theme = getattr(self, "theme", None)
        if isinstance(theme, str) and theme:
            cfg.set("textual.theme", theme)
        else:
            cfg.unset("textual.theme")
        cfg.save()

    def watch_theme(self, theme: str) -> None:
        # Persist immediately when theme changes (e.g. command palette) so crashes
        # don't lose the selected preference.
        if isinstance(theme, str) and theme:
            self._persist_theme_preference()

    def _format_cwd(self, cwd: Path) -> str:
        home_override = os.environ.get("HOST_HOME", "").strip()
        home = Path(home_override) if home_override else Path.home()
        try:
            rel = cwd.relative_to(home)
            parts = list(rel.parts)
            if not parts:
                return "~"
            if len(parts) <= 2:
                return "~/" + "/".join(parts)
            return "~/.../" + "/".join(parts[-2:])
        except ValueError:
            parts = list(cwd.parts)
            if len(parts) <= 3:
                return str(cwd)
            return "/.../" + "/".join(parts[-2:])

    def _cwd_text(self) -> str:
        host_cwd = os.environ.get("HOST_CWD", "").strip()
        cwd = Path(host_cwd) if host_cwd else Path.cwd()
        display = self._format_cwd(cwd)
        return f"CWD: {display}"

    def _refresh_cwd_bar(self) -> None:
        text = self._cwd_text()
        for widget in self.screen.query("#cwd-bar"):
            if not isinstance(widget, Static):
                continue
            widget.update(text)

    def get_system_commands(self, screen: Screen) -> Iterable[Any]:
        for command in super().get_system_commands(screen):
            title = getattr(command, "title", "")
            if isinstance(title, str) and "screenshot" in title.lower():
                continue
            yield command

    def on_unmount(self) -> None:
        self._persist_theme_preference()
