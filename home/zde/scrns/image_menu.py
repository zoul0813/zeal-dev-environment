from __future__ import annotations

from mods.tui.screens.file_tree import FileTreeScreen
from mods.tui.screens.item_action_screen import ActionResult, ItemAction, ItemActionScreen, ItemEntry


class ImageMenuScreen(ItemActionScreen):
    REFRESH_ACTION = False
    DEFAULT_ACTION_ID = "open"

    def __init__(self) -> None:
        super().__init__(
            title="Image Browser",
            subtitle="Select a media type, then open its staged file viewer",
            items_title="Media",
            actions_title="Actions",
        )

    def get_items(self) -> list[ItemEntry]:
        return [
            ItemEntry(id="eeprom", label="eeprom", action_ids=["open"]),
            ItemEntry(id="cf", label="cf", action_ids=["open"]),
            ItemEntry(id="tf", label="tf", action_ids=["open"]),
            ItemEntry(id="romdisk", label="romdisk", action_ids=["open"]),
        ]

    def get_actions(self) -> list[ItemAction]:
        return [ItemAction("open", "open", shortcut="f3", callback=self._action_open)]

    def _action_open(self, item: ItemEntry) -> ActionResult:
        self.app.push_screen(FileTreeScreen(item.id), lambda _result: self.action_focus_items())
        return ActionResult(status="", focus_items=False)
