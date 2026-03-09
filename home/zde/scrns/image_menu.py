from __future__ import annotations

from mods import image as image_mod
from mods.tui.exec import suspend_for_external_output
from mods.tui.screens.file_tree import FileTreeScreen
from mods.tui.screens.item_action_screen import ActionResult, ItemAction, ItemActionScreen, ItemEntry
from mods.tui.screens.prompt_modal import PromptModal


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
        rows: list[ItemEntry] = []
        for image in image_mod.images():
            action_ids = ["open"]
            if image.create_usage is not None:
                action_ids.append("create")
            rows.append(ItemEntry(id=image.image_type, label=image.image_type, action_ids=action_ids))
        return rows

    def get_actions(self) -> list[ItemAction]:
        return [
            ItemAction("open", "open", shortcut="f3", callback=self._action_open),
            ItemAction("create", "create", shortcut="f5", callback=self._action_create),
        ]

    def _action_open(self, item: ItemEntry) -> ActionResult:
        self.app.push_screen(FileTreeScreen(item.id), lambda _result: self.action_focus_items())
        return ActionResult(status="", focus_items=False)

    def _action_create(self, item: ItemEntry) -> ActionResult:
        image = image_mod.get_image(item.id)
        if item.id == "romdisk":
            with suspend_for_external_output(self.app):
                rc = int(image.create([]))
            self._pause_after_run()
            self.app.refresh(layout=True, repaint=True)
            self.refresh(layout=True, repaint=True)
            self.action_focus_items()
            if rc == 0:
                self._set_status(f"[ok] created {item.id}")
                self._set_output("")
                return ActionResult(status="")
            self._set_status(f"[error] create failed ({rc}) for {item.id}")
            self._set_output("")
            return ActionResult(status="")

        default_size = image.default_create_size
        if default_size is None:
            return ActionResult(rc=1, status=f"[warn] create is not supported for {item.id}")
        self.app.push_screen(
            PromptModal(
                title=f"Create {item.id} Image",
                detail="Enter the image size.",
                placeholder=default_size,
                initial_value=default_size,
                submit_label="Create",
                cancel_label="Cancel",
                empty_allowed=False,
            ),
            lambda value: self._on_create_size(item.id, value),
        )
        return ActionResult(status="")

    def _on_create_size(self, image_type: str, value: str | None) -> None:
        if value is None:
            self._set_status("")
            self.action_focus_items()
            return
        size = value.strip()
        if not size:
            self._set_status("[warn] Image size cannot be empty")
            self.action_focus_items()
            return

        image = image_mod.get_image(image_type)
        with suspend_for_external_output(self.app):
            rc = int(image.create([size]))
        self._pause_after_run()
        self.app.refresh(layout=True, repaint=True)
        self.refresh(layout=True, repaint=True)
        self.action_focus_items()
        if rc == 0:
            self._set_status(f"[ok] created {image_type} ({size})")
            self._set_output("")
            return
        self._set_status(f"[error] create failed ({rc}) for {image_type}")
        self._set_output("")
