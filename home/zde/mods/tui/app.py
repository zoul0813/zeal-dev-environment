from __future__ import annotations

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from mods.tui.catalog import build_catalog
from mods.tui.contract import CommandSpec
from mods.tui.exec import run_action


class ActionMenuScreen(Screen[None]):
    BINDINGS = [("escape", "app.pop_screen", "Back")]

    def __init__(self, command: CommandSpec) -> None:
        super().__init__()
        self._command = command

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static(f"Command: {self._command.label}"),
            Static("Select an action and press Enter"),
            ListView(id="actions"),
            Static("", id="status"),
        )
        yield Footer()

    def on_mount(self) -> None:
        actions = self.query_one("#actions", ListView)
        for action in self._command.actions:
            label = action.label if not action.help else f"{action.label} - {action.help}"
            actions.append(ListItem(Label(label), name=action.id))

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "actions" or event.item is None:
            return
        action_id = event.item.name or ""
        action = next((item for item in self._command.actions if item.id == action_id), None)
        if action is None:
            return
        rc = run_action(self._command.name, action.id, action.default_args)
        status = self.query_one("#status", Static)
        if rc == 0:
            status.update(f"[ok] Completed: {self._command.name} {action.id}")
            return
        status.update(f"[error] Failed ({rc}): {self._command.name} {action.id}")


class CommandMenuScreen(Screen[None]):
    def __init__(self, commands: list[CommandSpec]) -> None:
        super().__init__()
        self._commands = commands

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("ZDE TUI"),
            Static("Select a command and press Enter"),
            ListView(id="commands"),
        )
        yield Footer()

    def on_mount(self) -> None:
        commands = self.query_one("#commands", ListView)
        for command in self._commands:
            label = command.label if not command.help else f"{command.label} - {command.help}"
            commands.append(ListItem(Label(label), name=command.name))
        commands.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "commands" or event.item is None:
            return
        command_name = event.item.name or ""
        command = next((item for item in self._commands if item.name == command_name), None)
        if command is None:
            return
        self.app.push_screen(ActionMenuScreen(command))


class ZDEApp(App[None]):
    CSS = """
    Screen {
      padding: 1;
    }
    ListView {
      height: 1fr;
      border: round $panel;
      margin-top: 1;
    }
    #status {
      margin-top: 1;
      color: $text;
    }
    """

    def on_mount(self) -> None:
        commands = build_catalog()
        self.push_screen(CommandMenuScreen(commands))
