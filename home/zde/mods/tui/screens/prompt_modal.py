from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static


class PromptModal(ModalScreen[str | None]):
    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "submit", "Submit"),
    ]

    def __init__(
        self,
        *,
        title: str,
        detail: str = "",
        placeholder: str = "",
        initial_value: str = "",
        submit_label: str = "OK",
        cancel_label: str = "Cancel",
        empty_allowed: bool = False,
    ) -> None:
        super().__init__()
        self._title = title
        self._detail = detail
        self._placeholder = placeholder
        self._initial_value = initial_value
        self._submit_label = submit_label
        self._cancel_label = cancel_label
        self._empty_allowed = empty_allowed

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(self._title),
            Static(self._detail),
            Input(value=self._initial_value, placeholder=self._placeholder, id="prompt-input"),
            Static("", id="prompt-error"),
            Horizontal(
                Button(self._submit_label, id="prompt-submit"),
                Button(self._cancel_label, id="prompt-cancel"),
                id="prompt-actions",
            ),
            id="prompt-dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#prompt-input", Input).focus()

    def action_submit(self) -> None:
        value = self.query_one("#prompt-input", Input).value.strip()
        if not value and not self._empty_allowed:
            self.query_one("#prompt-error", Static).update("Value cannot be empty.")
            return
        self.dismiss(value)

    def action_cancel(self) -> None:
        self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prompt-submit":
            self.action_submit()
            return
        if event.button.id == "prompt-cancel":
            self.action_cancel()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "prompt-input":
            self.action_submit()
