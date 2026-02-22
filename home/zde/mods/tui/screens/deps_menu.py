from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from cmds import image as image_cmd
from mods.deps import Dep, DepCatalog
from mods.tui.exec import clear_terminal
from mods.tui.screens.choice_modal import ChoiceModal
from mods.tui.screens.item_action_screen import ActionResult, ItemAction, ItemActionScreen


class DepsInfoModal(ModalScreen[None]):
    BINDINGS = [
        ("escape", "dismiss_modal", "Close"),
        ("q", "dismiss_modal", "Close"),
    ]

    def __init__(self, dep_id: str, content: str) -> None:
        super().__init__()
        self._dep_id = dep_id
        self._content = content

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static(f"Dependency Info: {self._dep_id}"),
            Static("Press Esc or q to close"),
            VerticalScroll(
                Static(self._content or "(no output)", id="deps-info-content"),
                id="deps-info-body",
            ),
            id="deps-info-dialog",
        )

    def action_dismiss_modal(self) -> None:
        self.dismiss(None)


class DepsMenuScreen(ItemActionScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("left", "focus_items", "Packages"),
        ("right", "focus_actions", "Actions"),
        ("f3", "run_info", "Info"),
        ("f5", "run_install", "Install"),
        ("f6", "run_build", "Build"),
        ("f7", "run_stage", "Stage"),
        ("f8", "run_remove", "Remove"),
        ("f2", "run_refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__(
            title="Dependencies",
            subtitle="Select a dependency, then choose an action",
            items_title="Packages",
            actions_title="Actions",
        )
        self._pending_stage_target: str | None = None
        self._stage_targets = set(image_cmd.available_stage_targets())

    def get_actions(self) -> list[ItemAction]:
        return [
            ItemAction("info", "info"),
            ItemAction("install", "install"),
            ItemAction("build", "build"),
            ItemAction("stage", "stage"),
            ItemAction("remove", "remove"),
            ItemAction("refresh", "refresh", requires_item=False),
        ]

    def get_default_action_id(self) -> str | None:
        return "info"

    def is_action_visible(self, action_id: str, item_id: str | None) -> bool:
        if action_id != "stage":
            return True
        if not isinstance(item_id, str):
            return False
        dep = self._dep_for_id(item_id)
        if dep is None:
            return False
        return len(dep.artifact_paths()) > 0

    def get_items(self) -> list[tuple[str, Text]]:
        rows: list[tuple[str, Text]] = []
        catalog = DepCatalog()

        for dep in catalog.deps:
            line = Text()
            marker = dep.marker
            if dep.state == "required-miss":
                line.append(marker, style="red")
            elif dep.state.startswith("broken"):
                line.append(marker, style="yellow")
            elif dep.installed and dep.tracked:
                line.append(marker, style="green")
            elif dep.installed and not dep.tracked:
                line.append(marker, style="yellow")
            else:
                line.append(marker)

            line.append(f" {dep.display_name}")
            if dep.state == "required-miss":
                line.append(" [required-miss]", style="red")
            elif dep.state.startswith("broken"):
                line.append(f" [{dep.state}]", style="yellow")
            if dep.installed and not dep.tracked:
                line.append(" [untracked]", style="yellow")

            rows.append((dep.id, line))
        return rows

    def _run_capture(self, fn, *args) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = int(fn(*args))
        return rc, out.getvalue().rstrip()

    def _dep_for_id(self, dep_id: str) -> Dep | None:
        catalog = DepCatalog()
        return catalog.get(dep_id)

    def _on_stage_target(self, dep_id: str, value: str | None) -> None:
        if value is None:
            self._set_status("")
            self.action_focus_items()
            return
        target = value.strip().lower()
        if target in self._stage_targets:
            self._pending_stage_target = target
            self._execute_action("stage", dep_id)
            return
        supported = ", ".join(sorted(self._stage_targets))
        self._set_status(f"[warn] Target must be one of: {supported}")
        self.action_focus_items()

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        if action_id == "refresh":
            return ActionResult(status="[ok] refreshed", refresh_items=True, preferred_item_id=self._last_item_id)
        if item_id is None:
            return ActionResult(rc=1, status="[warn] No dependency selected")

        dep = self._dep_for_id(item_id)
        if dep is None:
            return ActionResult(rc=1, status=f"[error] Unknown dependency: {item_id}")

        if action_id == "info":
            output = dep.render_info()
            if output:
                self.app.push_screen(DepsInfoModal(item_id, output), lambda _result: self.action_focus_items())
            return ActionResult(rc=0, output="")

        if action_id == "install":
            with self.app.suspend():
                clear_terminal()
                rc = int(dep.install())
            return ActionResult(rc=rc, output="", refresh_items=True, preferred_item_id=item_id)

        if action_id == "remove":
            rc, output = self._run_capture(dep.remove)
            return ActionResult(rc=rc, output=output, refresh_items=True, preferred_item_id=item_id)

        if action_id == "build":
            with self.app.suspend():
                clear_terminal()
                rc = int(dep.build())
                try:
                    input("\nPress Enter to return to ZDE TUI...")
                except EOFError:
                    pass
            return ActionResult(rc=rc, refresh_items=True, preferred_item_id=item_id)

        if action_id == "stage":
            if self._pending_stage_target is None:
                self.app.push_screen(
                    ChoiceModal(
                        title="Stage Artifacts Target",
                        detail="Select destination",
                        options=[(target, target) for target in image_cmd.available_stage_targets()],
                    ),
                    lambda value: self._on_stage_target(item_id, value),
                )
                return ActionResult(status="")
            target = self._pending_stage_target
            self._pending_stage_target = None
            rc, output = self._run_capture(dep.stage, target)
            return ActionResult(rc=rc, output=output, preferred_item_id=item_id)

        return ActionResult(rc=0)

    def action_run_info(self) -> None:
        self._run_shortcut_action("info")

    def action_run_install(self) -> None:
        self._run_shortcut_action("install")

    def action_run_build(self) -> None:
        self._run_shortcut_action("build")

    def action_run_stage(self) -> None:
        self._run_shortcut_action("stage")

    def action_run_remove(self) -> None:
        self._run_shortcut_action("remove")

    def action_run_refresh(self) -> None:
        self._run_shortcut_action("refresh")
