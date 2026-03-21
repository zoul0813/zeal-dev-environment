from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static


class TextViewModal(ModalScreen[None]):
    BINDINGS = [
        ("escape", "dismiss_modal", "Close"),
        ("q", "dismiss_modal", "Close"),
    ]

    def __init__(self, title: str, content: str, detail: str = "Press Esc or q to close") -> None:
        super().__init__()
        self._title = title
        self._content = content
        self._detail = detail

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._title),
            Static(self._detail),
            VerticalScroll(
                Static(self._content or "(no output)", id="text-view-content"),
                id="text-view-body",
            ),
            id="text-view-dialog",
        )

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)
