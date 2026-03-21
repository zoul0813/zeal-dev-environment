from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmModal(ModalScreen[bool]):
    BINDINGS = [
        ("y", "confirm", "Yes"),
        ("n", "cancel", "No"),
        ("escape", "cancel", "No"),
        ("left", "focus_prev_button", "Prev"),
        ("right", "focus_next_button", "Next"),
    ]

    def __init__(
        self,
        title: str = "Confirm?",
        detail: str = "Press Y/Enter to confirm, N/Esc to cancel.",
        yes_label: str = "Yes",
        no_label: str = "No",
        default_no: bool = True,
    ) -> None:
        super().__init__()
        self._title = title
        self._detail = detail
        self._yes_label = yes_label
        self._no_label = no_label
        self._default_no = default_no

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._title),
            Static(self._detail),
            Horizontal(
                Button(self._yes_label, id="confirm-yes"),
                Button(self._no_label, id="confirm-no"),
                id="quit-actions",
            ),
            id="quit-dialog",
        )

    def on_mount(self) -> None:
        focus_id = "confirm-no" if self._default_no else "confirm-yes"
        self.query_one(f"#{focus_id}", Button).focus()

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "confirm-yes":
            self.dismiss(True)
            return
        if event.button.id == "confirm-no":
            self.dismiss(False)

    def action_focus_prev_button(self) -> None:
        order = ["confirm-yes", "confirm-no"]
        focused = self.focused
        if isinstance(focused, Button) and focused.id in order:
            idx = order.index(focused.id)
            target = order[max(0, idx - 1)]
            self.query_one(f"#{target}", Button).focus()
            return
        focus_id = "confirm-no" if self._default_no else "confirm-yes"
        self.query_one(f"#{focus_id}", Button).focus()

    def action_focus_next_button(self) -> None:
        order = ["confirm-yes", "confirm-no"]
        focused = self.focused
        if isinstance(focused, Button) and focused.id in order:
            idx = order.index(focused.id)
            target = order[min(len(order) - 1, idx + 1)]
            self.query_one(f"#{target}", Button).focus()
            return
        focus_id = "confirm-no" if self._default_no else "confirm-yes"
        self.query_one(f"#{focus_id}", Button).focus()
