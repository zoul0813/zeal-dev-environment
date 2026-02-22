from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from cmds import image as image_cmd
from mods.tui.screens.item_action_screen import (
    ActionResult,
    ConfirmRequest,
    ItemAction,
    ItemEntry,
    ItemActionScreen,
)


class FileTreeScreen(ItemActionScreen):
    DEFAULT_ACTION_ID = "refresh"

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
            ItemAction("open", "open", shortcut="f3", callback=self._action_open),
            ItemAction("remove", "remove", shortcut="f8", callback=self._action_remove),
        ]

    def is_action_visible(self, action_id: str, item_id: str | None) -> bool:
        if action_id == "open":
            return isinstance(item_id, str) and self._entry_is_dir.get(item_id, False)
        if action_id == "remove":
            return item_id != ".."
        return True

    def preferred_action_id(self, item_id: str | None) -> str | None:
        if isinstance(item_id, str) and self._entry_is_dir.get(item_id, False):
            return "open"
        return "refresh"

    def get_items(self) -> list[ItemEntry]:
        rows: list[ItemEntry] = []
        self._entry_is_dir = {}
        if self._current_dir != Path("."):
            rows.append(ItemEntry(id="..", label="drwx ..", action_ids=["open", "refresh"]))
            self._entry_is_dir[".."] = True
        for name, line, is_dir in image_cmd.image_entries(self._image_type, self._current_dir):
            action_ids = ["remove", "refresh"]
            if is_dir:
                action_ids.append("open")
            rows.append(ItemEntry(id=name, label=line, action_ids=action_ids))
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

    def _action_open(self, item: ItemEntry) -> ActionResult:
        if self._navigate_to(item.id):
            self._last_item_id = None
            location = "." if self._current_dir == Path(".") else str(self._current_dir)
            return ActionResult(
                rc=0,
                status=f"[ok] opened {location}",
                refresh_items=True,
                preferred_item_id=None,
            )
        return ActionResult(rc=1, status="[warn] Selected item is not a directory")

    def _action_remove(self, item: ItemEntry) -> ActionResult:
        if item.id == "..":
            return ActionResult(rc=1, status="[warn] Select a file or directory entry")
        target = self._relative_target(item.id)
        rc, _output = self._run_capture(image_cmd.run_image_subcommand, self._image_type, ["rm", target])
        return ActionResult(
            rc=rc,
            output="",
            refresh_items=True,
            preferred_item_id=item.id,
            status=f"[ok] removed {target}" if rc == 0 else None,
        )

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
