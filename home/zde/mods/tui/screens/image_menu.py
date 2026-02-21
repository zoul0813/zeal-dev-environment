from __future__ import annotations

from mods.tui.screens.file_tree import FileTreeScreen
from mods.tui.screens.item_action_screen import ActionResult, ItemAction, ItemActionScreen


class ImageMenuScreen(ItemActionScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("left", "focus_items", "Media"),
        ("right", "focus_actions", "Actions"),
        ("f3", "run_open", "Open"),
    ]

    def __init__(self) -> None:
        super().__init__(
            title="Image Browser",
            subtitle="Select a media type, then open its staged file viewer",
            items_title="Media",
            actions_title="Actions",
        )

    def get_items(self) -> list[tuple[str, str]]:
        return [
            ("eeprom", "eeprom"),
            ("cf", "cf"),
            ("tf", "tf"),
            ("romdisk", "romdisk"),
        ]

    def get_actions(self) -> list[ItemAction]:
        return [ItemAction("open", "open")]

    def get_default_action_id(self) -> str | None:
        return "open"

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        if action_id == "open" and item_id is not None:
            self.app.push_screen(FileTreeScreen(item_id))
            return ActionResult(status="", focus_items=False)
        return ActionResult(rc=0)

    def action_run_open(self) -> None:
        self._run_shortcut_action("open")
