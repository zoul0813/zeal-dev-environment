from __future__ import annotations

from collections.abc import Iterable
import os
from pathlib import Path
from typing import Any

from textual.app import App
from textual.screen import Screen
from textual.widgets import Static

from mods.tui.catalog import build_catalog
from mods.tui.screens.command_menu import CommandMenuScreen
from mods.tui.settings import load_tui_preferences, save_tui_preferences


class ZDEApp(App[None]):
    TITLE = "Zeal Dev Environment"
    SUB_TITLE = "Terminal UI"

    CSS = """
    Screen {
      padding: 1;
    }
    .main-body {
      height: 1fr;
    }
    HeaderIcon {
      display: none;
    }
    ListView {
      height: 1fr;
      border: round $panel;
      margin-top: 1;
    }
    /* Force a strong highlighted-row contrast across themes. */
    ListItem.-highlight,
    ListItem.--highlight,
    ListView > .-highlight,
    ListView > .--highlight {
      background: $primary;
      color: $text;
      text-style: bold;
    }
    ListItem.-highlight Label,
    ListItem.--highlight Label,
    ListView > .-highlight Label,
    ListView > .--highlight Label {
      color: $text;
      text-style: bold;
    }
    /* Command palette uses OptionList/Option classes, not ListView/ListItem. */
    CommandPalette OptionList > .option--highlighted,
    CommandPalette OptionList > .option--highlight,
    CommandPalette OptionList > .--highlight,
    CommandPalette .option-list--option-highlighted,
    CommandPalette .option-list--highlighted {
      background: $primary;
      color: $text;
      text-style: bold;
    }
    CommandPalette OptionList > .option--highlighted Label,
    CommandPalette OptionList > .option--highlight Label,
    CommandPalette OptionList > .--highlight Label,
    CommandPalette .option-list--option-highlighted Label,
    CommandPalette .option-list--highlighted Label {
      color: $text;
      text-style: bold;
    }
    .status-line {
      color: $text;
      display: none;
      height: auto;
      margin-top: 0;
    }
    .status-line.show {
      display: block;
    }
    #cwd-bar {
      margin-top: 0;
      color: $text;
      background: $surface;
      padding: 0 1 0 1;
      border: none;
      height: 1;
    }
    ConfirmModal {
      align: center middle;
    }
    DepsInfoModal {
      align: center middle;
    }
    TextViewModal {
      align: center middle;
    }
    PromptModal {
      align: center middle;
    }
    ChoiceModal {
      align: center middle;
    }
    #quit-dialog {
      width: 44;
      height: auto;
      border: round $accent;
      background: $panel;
      padding: 1 2;
    }
    #quit-actions {
      margin-top: 1;
      align-horizontal: center;
      height: auto;
    }
    #quit-actions Button {
      width: 12;
      margin: 0 1;
    }
    #deps-info-dialog {
      width: 85%;
      height: 85%;
      border: round $accent;
      background: $panel;
      padding: 1 2;
    }
    #deps-info-body {
      height: 1fr;
      margin-top: 1;
      border: round $panel-darken-1;
      padding: 0 1;
    }
    #text-view-dialog {
      width: 85%;
      height: 85%;
      border: round $accent;
      background: $panel;
      padding: 1 2;
    }
    #text-view-body {
      height: 1fr;
      margin-top: 1;
      border: round $panel-darken-1;
      padding: 0 1;
    }
    #prompt-dialog {
      width: 56;
      height: auto;
      border: round $accent;
      background: $panel;
      padding: 1 2;
    }
    #prompt-actions {
      margin-top: 1;
      align-horizontal: center;
      height: auto;
    }
    #prompt-actions Button {
      width: 12;
      margin: 0 1;
    }
    #prompt-error {
      color: $warning;
      height: auto;
    }
    #choice-dialog {
      width: 56;
      height: auto;
      border: round $accent;
      background: $panel;
      padding: 1 2;
    }
    #choice-options {
      margin-top: 1;
      height: 12;
    }
    #item-list-panel,
    #item-actions-panel {
      border: round $panel-darken-2;
      padding: 0 1;
      margin-right: 1;
    }
    #item-list-panel {
      width: 1fr;
    }
    #item-actions-panel {
      width: 24;
      margin-right: 0;
    }
    #item-list-panel.active-panel,
    #item-actions-panel.active-panel {
      border: round $primary;
    }
    #item-layout {
      height: 1fr;
    }
    #commands-layout {
      height: 1fr;
    }
    #commands-list-panel {
      width: 1fr;
      border: round $panel-darken-2;
      padding: 0 1;
      margin-right: 0;
    }
    #commands-list-panel.active-panel {
      border: round $primary;
    }
    #actions-layout {
      height: 1fr;
    }
    #actions-list-panel {
      width: 1fr;
      border: round $panel-darken-2;
      padding: 0 1;
      margin-right: 0;
    }
    #actions-list-panel.active-panel {
      border: round $primary;
    }
    #item-list ListItem.item-selected {
      background: $primary;
      color: $text;
      text-style: bold;
    }
    #item-list ListItem.item-selected Label {
      color: $text;
      text-style: bold;
    }
    #item-actions ListItem.action-selected {
      background: $primary;
      color: $text;
      text-style: bold;
    }
    #item-actions ListItem.action-selected Label {
      color: $text;
      text-style: bold;
    }
    """

    def on_mount(self) -> None:
        prefs = load_tui_preferences()
        theme = prefs.get("theme")
        if not isinstance(theme, str) or not theme:
            theme = "solarized-dark"
        if isinstance(theme, str) and theme:
            try:
                self.theme = theme
            except Exception:
                pass
        dark = prefs.get("dark")
        if isinstance(dark, bool):
            self.dark = dark
        commands = build_catalog()
        self.push_screen(CommandMenuScreen(commands))
        self._refresh_cwd_bar()
        self.set_interval(1.0, self._refresh_cwd_bar)

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
        save_tui_preferences(getattr(self, "theme", None), bool(getattr(self, "dark", False)))
