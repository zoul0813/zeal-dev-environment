from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cmds import image as image_cmd
from mods.tui.screens.item_action_screen import (
    ActionResult,
    ConfirmRequest,
    ItemAction,
    ItemActionScreen,
)


class FileTreeScreen(ItemActionScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("left", "focus_items", "Entries"),
        ("right", "focus_actions", "Actions"),
        ("f8", "run_remove", "Remove"),
        ("f2", "run_refresh", "Refresh"),
    ]

    def __init__(self, image_type: str) -> None:
        self._image_type = image_type
        self._current_dir = Path(".")
        self._entry_is_dir: dict[str, bool] = {}
        super().__init__(
            title=f"Image: {image_type}",
            subtitle=f"Browse staged files for {image_type}",
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
        rows: list[tuple[str, str]] = []
        self._entry_is_dir = {}
        if self._current_dir != Path("."):
            rows.append(("..", "drwx             .."))
            self._entry_is_dir[".."] = True
        for name, line, is_dir in image_cmd.image_entries(self._image_type, self._current_dir):
            rows.append((name, line))
            self._entry_is_dir[name] = is_dir
        return rows

    def _run_capture(self, fn, *args) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = int(fn(*args))
        return rc, out.getvalue().rstrip()

    def confirm_action(self, action_id: str, item_id: str | None) -> ConfirmRequest | None:
        if item_id == "..":
            return None
        if action_id != "remove" or item_id is None:
            return None
        target = self._relative_target(item_id)
        return ConfirmRequest(
            title=f"Remove '{target}' from {self._image_type}?",
            detail="Press Y to remove, N/Esc to cancel.",
            yes_label="Remove",
            no_label="Cancel",
            default_no=True,
        )

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        if action_id == "refresh":
            return ActionResult(status="[ok] refreshed", refresh_items=True, preferred_item_id=self._last_item_id)
        if item_id == "..":
            return ActionResult(rc=1, status="[warn] Select a file or directory entry")
        if action_id == "remove" and item_id is not None:
            target = self._relative_target(item_id)
            rc, output = self._run_capture(image_cmd.run_image_subcommand, self._image_type, ["rm", target])
            return ActionResult(
                rc=rc,
                output="",
                refresh_items=True,
                preferred_item_id=item_id,
                status=f"[ok] removed {target}" if rc == 0 else None,
            )
        return ActionResult(rc=0)

    def _relative_target(self, item_id: str) -> str:
        if self._current_dir == Path("."):
            return item_id
        return str(self._current_dir / item_id)

    def _navigate_to(self, item_id: str) -> bool:
        if item_id == "..":
            if self._current_dir == Path("."):
                return False
            self._current_dir = self._current_dir.parent
            return True
        if not self._entry_is_dir.get(item_id, False):
            return False
        self._current_dir = self._current_dir / item_id
        return True

    def on_key(self, event) -> None:
        if event.key == "enter":
            focused = self.app.focused
            focused_id = getattr(focused, "id", "")
            if focused_id == "item-list":
                selected = self._selected_item_id()
                if isinstance(selected, str) and self._navigate_to(selected):
                    self._last_item_id = None
                    self._refresh_items()
                    self.action_focus_items()
                    location = "." if self._current_dir == Path(".") else str(self._current_dir)
                    self._set_status(f"[ok] opened {location}")
                    event.stop()
                    event.prevent_default()
                    return
        super().on_key(event)

    def action_run_refresh(self) -> None:
        self._run_shortcut_action("refresh")

    def action_run_remove(self) -> None:
        self._run_shortcut_action("remove")
