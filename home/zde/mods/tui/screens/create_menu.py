from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from cmds import create as create_cmd
from mods.tui.screens.item_action_screen import ActionResult, ItemAction, ItemActionScreen
from mods.tui.screens.prompt_modal import PromptModal
from mods.tui.screens.text_view_modal import TextViewModal


class CreateMenuScreen(ItemActionScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("left", "focus_items", "Templates"),
        ("right", "focus_actions", "Actions"),
        ("f5", "run_create", "Create"),
    ]

    def __init__(self) -> None:
        super().__init__(
            title="Create Project",
            subtitle="Select a template, then run create",
            items_title="Templates",
            actions_title="Actions",
        )
        self._pending_project_name: str | None = None

    def get_actions(self) -> list[ItemAction]:
        return [ItemAction("create", "create")]

    def get_items(self) -> list[tuple[str, str]]:
        names = create_cmd.list_templates()
        return [(name, name) for name in names]

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        if action_id != "create" or item_id is None:
            return ActionResult(rc=0)
        if self._pending_project_name is None:
            self.app.push_screen(
                PromptModal(
                    title="Project Name",
                    detail="Enter the new project folder name.",
                    placeholder="my-project",
                    submit_label="Create",
                    cancel_label="Cancel",
                ),
                lambda value: self._on_project_name(item_id, value),
            )
            return ActionResult(status="")

        project_name = self._pending_project_name
        self._pending_project_name = None
        rc, output = self._run_capture(create_cmd.main, [item_id, f"--name={project_name}"])
        if rc != 0:
            self.app.push_screen(
                TextViewModal(
                    title=f"Create Failed ({item_id})",
                    content=output or "Create failed with no output.",
                ),
                lambda _result: self.action_focus_items(),
            )
        return ActionResult(rc=rc, preferred_item_id=item_id)

    def action_run_create(self) -> None:
        self._run_shortcut_action("create")

    def _on_project_name(self, template_id: str, value: str | None) -> None:
        if value is None:
            self._set_status("")
            self.action_focus_items()
            return
        self._pending_project_name = value
        self._execute_action("create", template_id)

    def _run_capture(self, fn, *args) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = int(fn(*args))
        return rc, out.getvalue().rstrip()
