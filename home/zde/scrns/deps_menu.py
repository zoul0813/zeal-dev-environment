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
from mods.tui.exec import suspend_for_external_output
from mods.tui.screens.choice_modal import ChoiceModal
from mods.tui.screens.item_action_screen import ActionResult, ItemAction, ItemActionScreen, ItemEntry


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
    DEFAULT_ACTION_ID = "info"

    def __init__(self) -> None:
        super().__init__(
            title="Dependencies",
            subtitle="Select a dependency, then choose an action",
            items_title="Packages",
            actions_title="Actions",
        )
        self._pending_stage_target: str | None = None
        self._stage_targets = set(image_cmd.available_stage_targets())
        self._category_filter: str | None = None

    def on_mount(self) -> None:
        super().on_mount()
        self._update_items_title()

    def get_actions(self) -> list[ItemAction]:
        return [
            ItemAction("filter", "filter", requires_item=False, shortcut="f9"),
            ItemAction("info", "info", shortcut="f3", callback=self._action_info),
            ItemAction("update", "update", shortcut="f4", callback=self._action_update),
            ItemAction("install", "install", shortcut="f5", callback=self._action_install),
            ItemAction("build", "build", shortcut="f6", callback=self._action_build),
            ItemAction("stage", "stage", shortcut="f7", callback=self._action_stage),
            ItemAction("remove", "remove", shortcut="f8", callback=self._action_remove),
        ]

    def get_items(self) -> list[ItemEntry]:
        rows: list[ItemEntry] = []
        catalog = DepCatalog()
        deps = catalog.deps if self._category_filter is None else catalog.category(self._category_filter)

        for dep in deps:
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

            action_ids = ["info", "update", "install", "build", "remove"]
            if len(dep.artifact_paths()) > 0:
                action_ids.append("stage")
            rows.append(ItemEntry(id=dep.id, label=line, action_ids=action_ids, data=dep))
        return rows

    def _run_capture(self, fn, *args) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = int(fn(*args))
        return rc, out.getvalue().rstrip()

    def _update_items_title(self) -> None:
        title = "Packages"
        if self._category_filter:
            title = f"Packages ({self._category_filter})"
        panel = self.query_one("#item-list-panel", Vertical)
        for child in panel.children:
            if isinstance(child, Static):
                child.update(title)
                break

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        if action_id == "filter":
            return self._action_filter()
        return super().run_action(action_id, item_id)

    def _dep_from_item(self, item: ItemEntry) -> Dep:
        dep = item.data
        if not isinstance(dep, Dep):
            raise ValueError(f"Invalid dependency item payload for {item.id}")
        return dep

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

    def _on_filter_selected(self, value: str | None) -> None:
        if value is None:
            self._set_status("")
            self.action_focus_items()
            return

        chosen = value.strip()
        self._category_filter = chosen or None
        self._update_items_title()
        self._refresh_items(preferred_item_id=self._last_item_id)
        self._ensure_item_selection()
        self._refresh_actions(preferred_action_id="filter")
        if self._category_filter is None:
            self._set_status("[ok] category filter: all")
        else:
            self._set_status(f"[ok] category filter: {self._category_filter}")
        self._set_output("")
        self.action_focus_items()

    def _action_filter(self) -> ActionResult:
        catalog = DepCatalog()
        options = [("", "all")]
        options.extend((category, category) for category in catalog.categories)
        self.app.push_screen(
            ChoiceModal(
                title="Dependency Filter",
                detail="Select a category",
                options=options,
            ),
            self._on_filter_selected,
        )
        return ActionResult(status="")

    def _action_info(self, item: ItemEntry) -> ActionResult:
        dep = self._dep_from_item(item)
        output = dep.render_info()
        if output:
            self.app.push_screen(DepsInfoModal(dep.id, output), lambda _result: self.action_focus_items())
        return ActionResult(rc=0, output="")

    def _action_install(self, item: ItemEntry) -> ActionResult:
        dep = self._dep_from_item(item)
        with suspend_for_external_output(self.app):
            rc = int(dep.install())
        return ActionResult(rc=rc, output="", refresh_items=True, preferred_item_id=dep.id)

    def _action_update(self, item: ItemEntry) -> ActionResult:
        dep = self._dep_from_item(item)
        with suspend_for_external_output(self.app):
            rc = int(dep.update())
        return ActionResult(rc=rc, output="", refresh_items=True, preferred_item_id=dep.id)

    def _action_remove(self, item: ItemEntry) -> ActionResult:
        dep = self._dep_from_item(item)
        rc, output = self._run_capture(dep.remove)
        return ActionResult(rc=rc, output=output, refresh_items=True, preferred_item_id=dep.id)

    def _action_build(self, item: ItemEntry) -> ActionResult:
        dep = self._dep_from_item(item)
        with suspend_for_external_output(self.app):
            rc = int(dep.build())
            try:
                input("\nPress Enter to return to ZDE TUI...")
            except EOFError:
                pass
        return ActionResult(rc=rc, refresh_items=True, preferred_item_id=dep.id)

    def _action_stage(self, item: ItemEntry) -> ActionResult:
        dep = self._dep_from_item(item)
        if self._pending_stage_target is None:
            self.app.push_screen(
                ChoiceModal(
                    title="Stage Artifacts Target",
                    detail="Select destination",
                    options=[(target, target) for target in image_cmd.available_stage_targets()],
                ),
                lambda value: self._on_stage_target(dep.id, value),
            )
            return ActionResult(status="")
        target = self._pending_stage_target
        self._pending_stage_target = None
        rc, output = self._run_capture(dep.stage, target)
        return ActionResult(rc=rc, output=output, preferred_item_id=dep.id)
