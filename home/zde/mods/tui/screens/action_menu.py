from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from mods.tui.contract import CommandSpec
from mods.tui.exec import clear_terminal, run_action


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
            Horizontal(
                Vertical(
                    Static("Actions"),
                    ListView(id="actions"),
                    id="actions-list-panel",
                ),
                id="actions-layout",
            ),
            Static("", id="status", classes="status-line"),
            classes="main-body",
        )
        yield Static("", id="cwd-bar")
        yield Footer()

    def on_mount(self) -> None:
        actions = self.query_one("#actions", ListView)
        for action in self._command.actions:
            label = action.label if not action.help else f"{action.label} - {action.help}"
            actions.append(ListItem(Label(label), name=action.id))
        if self._command.actions:
            actions.index = 0
        actions.focus()
        self.query_one("#actions-list-panel", Vertical).add_class("active-panel")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "actions" or event.item is None:
            return
        action_id = event.item.name or ""
        action = next((item for item in self._command.actions if item.id == action_id), None)
        if action is None:
            return
        with self.app.suspend():
            clear_terminal()
            rc = run_action(self._command.name, action.id, action.default_args)
            if action.pause_after_run:
                try:
                    input("\nPress Enter to return to ZDE TUI...")
                except EOFError:
                    pass
        self.app.refresh(layout=True, repaint=True)
        self.refresh(layout=True, repaint=True)
        self.query_one("#actions", ListView).focus()
        if rc == 0:
            self._set_status(f"[ok] Completed: {self._command.name} {action.id}")
            return
        self._set_status(f"[error] Failed ({rc}): {self._command.name} {action.id}")

    def _set_status(self, text: str) -> None:
        status = self.query_one("#status", Static)
        status.update(text)
        if text:
            status.add_class("show")
        else:
            status.remove_class("show")
