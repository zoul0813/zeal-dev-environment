from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from mods.commands import DEFAULT_MODULE_ALIASES, command_to_module_name, import_command_module
from mods.tui.contract import CommandSpec
from mods.tui.exec import run_action
from mods.tui.screens.action_menu import ActionMenuScreen
from mods.tui.screens.confirm_modal import ConfirmModal


class CommandMenuScreen(Screen[None]):
    BINDINGS = [("escape", "quit_prompt", "Quit")]

    def __init__(self, commands: list[CommandSpec]) -> None:
        super().__init__()
        self._commands = commands

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("Select a command and press Enter"),
            Horizontal(
                Vertical(
                    Static("Commands"),
                    ListView(id="commands"),
                    id="commands-list-panel",
                ),
                id="commands-layout",
            ),
            Static("", id="status", classes="status-line"),
            classes="main-body",
        )
        yield Static("", id="cwd-bar")
        yield Footer()

    def on_mount(self) -> None:
        commands = self.query_one("#commands", ListView)
        for command in self._commands:
            label = command.label if not command.help else f"{command.label} - {command.help}"
            commands.append(ListItem(Label(label), name=command.name))
        if self._commands:
            commands.index = 0
        commands.focus()
        self.query_one("#commands-list-panel", Vertical).add_class("active-panel")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "commands" or event.item is None:
            return
        command_name = event.item.name or ""
        command = next((item for item in self._commands if item.name == command_name), None)
        if command is None:
            return
        module_name = command_to_module_name(command.name, DEFAULT_MODULE_ALIASES)
        module = import_command_module(module_name)
        custom_screen = getattr(module, "get_tui_screen", None)
        if callable(custom_screen):
            screen = custom_screen()
            if isinstance(screen, Screen):
                self.app.push_screen(screen)
                return
        if len(command.actions) == 1:
            action = command.actions[0]
            with self.app.suspend():
                rc = run_action(command.name, action.id, action.default_args)
                if action.pause_after_run:
                    try:
                        input("\nPress Enter to return to ZDE TUI...")
                    except EOFError:
                        pass
            self.app.refresh(layout=True, repaint=True)
            self.refresh(layout=True, repaint=True)
            self.query_one("#commands", ListView).focus()
            if rc == 0:
                self._set_status(f"[ok] Completed: {command.name} {action.id}")
                return
            self._set_status(f"[error] Failed ({rc}): {command.name} {action.id}")
            return
        self.app.push_screen(ActionMenuScreen(command))

    def _set_status(self, text: str) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        if text:
            status.add_class("show")
        else:
            status.remove_class("show")

    def action_quit_prompt(self) -> None:
        self.app.push_screen(
            ConfirmModal(
                title="Quit ZDE TUI?",
                detail="Press Y to quit, N/Esc to stay.",
                yes_label="Yes",
                no_label="No",
                default_no=True,
            ),
            self._handle_quit_prompt,
        )

    def _handle_quit_prompt(self, should_quit: bool) -> None:
        if should_quit:
            self.app.exit()
