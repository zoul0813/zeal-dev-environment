from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView, Static


class ChoiceModal(ModalScreen[str | None]):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("q", "cancel", "Cancel"),
        ("enter", "select_current", "Select"),
    ]

    def __init__(self, *, title: str, detail: str, options: list[tuple[str, str]]) -> None:
        super().__init__()
        self._title = title
        self._detail = detail
        self._options = options

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._title),
            Static(self._detail),
            ListView(id="choice-options"),
            id="choice-dialog",
        )

    def on_mount(self) -> None:
        options = self.query_one("#choice-options", ListView)
        for value, label in self._options:
            options.append(ListItem(Label(label), name=value))
        if options.children:
            options.index = 0
        options.focus()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "choice-options" or event.item is None:
            return
        value = event.item.name
        self.dismiss(value if isinstance(value, str) else None)

    def action_select_current(self) -> None:
        options = self.query_one("#choice-options", ListView)
        if options.highlighted_child is None:
            return
        value = options.highlighted_child.name
        self.dismiss(value if isinstance(value, str) else None)

    def action_cancel(self) -> None:
        self.dismiss(None)
