from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from cmds import create as create_cmd
from mods.tui.panels.item_action_screen import ActionResult, ItemAction, ItemActionScreen, ItemEntry
from mods.tui.modals.prompt_modal import PromptModal
from mods.tui.modals.text_view_modal import TextViewModal


class CreateMenuScreen(ItemActionScreen):
    REFRESH_ACTION = False
    DEFAULT_ACTION_ID = "create"

    def __init__(self) -> None:
        super().__init__(
            title="Create Project",
            subtitle="Select a template, then run create",
            items_title="Templates",
            actions_title="Actions",
        )

    def get_actions(self) -> list[ItemAction]:
        return [ItemAction("create", "create", shortcut="f5", callback=self._action_create)]

    def get_items(self) -> list[ItemEntry]:
        names = create_cmd.list_templates()
        return [ItemEntry(id=name, label=name, action_ids=["create"]) for name in names]

    def _action_create(self, item: ItemEntry) -> ActionResult:
        self.app.push_screen(
            PromptModal(
                title="Project Name",
                detail="Enter the new project folder name.",
                placeholder="my-project",
                submit_label="Create",
                cancel_label="Cancel",
            ),
            lambda value: self._on_project_name(item.id, value),
        )
        return ActionResult(status="")

    def _on_project_name(self, template_id: str, value: str | None) -> None:
        if value is None:
            self._set_status("")
            self.action_focus_items()
            return
        project_name = value.strip()
        if not project_name:
            self._set_status("[warn] Project name cannot be empty")
            self.action_focus_items()
            return

        rc, output = self._run_capture(create_cmd.main, [template_id, f"--name={project_name}"])
        if rc != 0:
            self.app.push_screen(
                TextViewModal(
                    title=f"Create Failed ({template_id})",
                    content=output or "Create failed with no output.",
                ),
                lambda _result: self.action_focus_items(),
            )
            self._set_status(f"[error] create failed ({rc}) for {template_id}")
        else:
            self._set_status(f"[ok] create {template_id}")
        self._set_output("")
        self.action_focus_items()
        self.app.refresh(layout=True, repaint=True)
        self.refresh(layout=True, repaint=True)

    def _run_capture(self, fn, *args) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = int(fn(*args))
        return rc, out.getvalue().rstrip()
