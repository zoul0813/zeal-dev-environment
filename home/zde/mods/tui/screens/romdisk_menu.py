from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from cmds import romdisk as romdisk_cmd
from mods.tui.screens.item_action_screen import (
    ActionResult,
    ConfirmRequest,
    ItemAction,
    ItemActionScreen,
)


class RomdiskMenuScreen(ItemActionScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("left", "focus_items", "Entries"),
        ("right", "focus_actions", "Actions"),
        ("f8", "run_remove", "Remove"),
        ("f2", "run_refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__(
            title="Romdisk",
            subtitle="Select a romdisk entry, then choose an action",
            items_title="Entries",
            actions_title="Actions",
        )

    def get_actions(self) -> list[ItemAction]:
        return [
            ItemAction("remove", "remove"),
            ItemAction("refresh", "refresh", requires_item=False),
        ]

    def get_default_action_id(self) -> str | None:
        return "refresh"

    def get_items(self) -> list[tuple[str, str]]:
        return romdisk_cmd._romdisk_rows()  # noqa: SLF001 - shared formatter

    def _run_capture(self, fn, *args) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = int(fn(*args))
        return rc, out.getvalue().rstrip()

    def confirm_action(self, action_id: str, item_id: str | None) -> ConfirmRequest | None:
        if action_id != "remove" or item_id is None:
            return None
        return ConfirmRequest(
            title=f"Remove '{item_id}'?",
            detail="Press Y to remove, N/Esc to cancel.",
            yes_label="Remove",
            no_label="Cancel",
            default_no=True,
        )

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        if action_id == "refresh":
            return ActionResult(status="[ok] refreshed", refresh_items=True, preferred_item_id=self._last_item_id)
        if action_id == "remove" and item_id is not None:
            rc, output = self._run_capture(romdisk_cmd.subcmd_rm, [item_id])
            return ActionResult(
                rc=rc,
                output="",
                refresh_items=True,
                preferred_item_id=item_id,
                status=f"[ok] removed {item_id}" if rc == 0 else None,
            )
        return ActionResult(rc=0)

    def action_run_refresh(self) -> None:
        self._run_shortcut_action("refresh")

    def action_run_remove(self) -> None:
        self._run_shortcut_action("remove")
