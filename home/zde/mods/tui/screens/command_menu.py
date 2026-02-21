from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

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
            ListView(id="commands"),
            Static("", id="status"),
        )
        yield Footer()

    def on_mount(self) -> None:
        commands = self.query_one("#commands", ListView)
        for command in self._commands:
            label = command.label if not command.help else f"{command.label} - {command.help}"
            commands.append(ListItem(Label(label), name=command.name))
        if self._commands:
            commands.index = 0
        commands.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "commands" or event.item is None:
            return
        command_name = event.item.name or ""
        command = next((item for item in self._commands if item.name == command_name), None)
        if command is None:
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
            status = self.query_one("#status", Static)
            if rc == 0:
                status.update(f"[ok] Completed: {command.name} {action.id}")
                return
            status.update(f"[error] Failed ({rc}): {command.name} {action.id}")
            return
        self.app.push_screen(ActionMenuScreen(command))

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
