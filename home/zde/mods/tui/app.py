from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from textual.app import App
from textual.screen import Screen

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
    #status {
      margin-top: 1;
      color: $text;
    }
    ConfirmModal {
      align: center middle;
    }
    DepsInfoModal {
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
    #deps-list-panel,
    #deps-actions-panel {
      border: round $panel-darken-2;
      padding: 0 1;
      margin-right: 1;
    }
    #deps-actions-panel {
      margin-right: 0;
    }
    #deps-list-panel.active-panel,
    #deps-actions-panel.active-panel {
      border: round $primary;
    }
    #deps-list ListItem.deps-selected {
      background: $primary;
      color: $text;
      text-style: bold;
    }
    #deps-list ListItem.deps-selected Label {
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

    def get_system_commands(self, screen: Screen) -> Iterable[Any]:
        for command in super().get_system_commands(screen):
            title = getattr(command, "title", "")
            if isinstance(title, str) and "screenshot" in title.lower():
                continue
            yield command

    def on_unmount(self) -> None:
        save_tui_preferences(getattr(self, "theme", None), bool(getattr(self, "dark", False)))
