from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from mods.tui.screens.confirm_modal import ConfirmModal


@dataclass(frozen=True)
class ItemAction:
    id: str
    label: str
    requires_item: bool = True


@dataclass(frozen=True)
class ConfirmRequest:
    title: str
    detail: str
    yes_label: str = "Yes"
    no_label: str = "No"
    default_no: bool = True


@dataclass(frozen=True)
class ActionResult:
    rc: int = 0
    output: str = ""
    status: str | None = None
    refresh_items: bool = False
    preferred_item_id: str | None = None
    focus_items: bool = True


class ItemActionScreen(Screen[None]):
    def __init__(
        self,
        *,
        title: str,
        subtitle: str,
        items_title: str = "Items",
        actions_title: str = "Actions",
    ) -> None:
        super().__init__()
        self._title = title
        self._subtitle = subtitle
        self._items_title = items_title
        self._actions_title = actions_title
        self._last_item_id: str | None = None
        self._action_defs: dict[str, ItemAction] = {}

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static(self._title),
            Static(self._subtitle),
            Horizontal(
                Vertical(
                    Static(self._items_title),
                    ListView(id="item-list"),
                    id="item-list-panel",
                ),
                Vertical(
                    Static(self._actions_title),
                    ListView(id="item-actions"),
                    id="item-actions-panel",
                ),
                id="item-layout",
            ),
            Static("", id="item-status", classes="status-line"),
            Static("", id="item-output", classes="status-line"),
            classes="main-body",
        )
        yield Static("", id="cwd-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._action_defs = {action.id: action for action in self.get_actions()}
        actions = self.query_one("#item-actions", ListView)
        for action in self._action_defs.values():
            actions.append(ListItem(Label(action.label), name=action.id))
        if actions.children:
            default_id = self.get_default_action_id()
            if default_id is not None:
                for idx, child in enumerate(actions.children):
                    if child.name == default_id:
                        actions.index = idx
                        break
                else:
                    actions.index = 0
            else:
                actions.index = 0
        self._refresh_items()
        self.action_focus_items()

    def get_items(self) -> list[tuple[str, Any]]:
        raise NotImplementedError

    def get_actions(self) -> list[ItemAction]:
        raise NotImplementedError

    def confirm_action(self, action_id: str, item_id: str | None) -> ConfirmRequest | None:
        return None

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        return ActionResult(rc=0)

    def get_default_action_id(self) -> str | None:
        return None

    def _refresh_items(self, preferred_item_id: str | None = None) -> None:
        items = self.query_one("#item-list", ListView)
        clear_fn = getattr(items, "clear", None)
        if callable(clear_fn):
            clear_fn()
        else:
            while items.children:
                items.remove(items.children[0])

        rows = self.get_items()
        names: list[str] = []
        for item_id, label in rows:
            names.append(item_id)
            items.append(ListItem(Label(label), name=item_id))

        if not items.children:
            self._last_item_id = None
            return
        wanted = preferred_item_id or self._last_item_id
        if wanted and wanted in names:
            items.index = names.index(wanted)
            self._last_item_id = wanted
        else:
            items.index = 0
            if items.highlighted_child is not None and isinstance(items.highlighted_child.name, str):
                self._last_item_id = items.highlighted_child.name
        self._sync_item_selection_visual()

    def _selected_item_id(self) -> str | None:
        items = self.query_one("#item-list", ListView)
        if items.highlighted_child is None:
            return self._last_item_id
        selected = items.highlighted_child.name
        if isinstance(selected, str):
            self._last_item_id = selected
            return selected
        return None

    def _ensure_item_selection(self) -> None:
        items = self.query_one("#item-list", ListView)
        if not items.children:
            self._last_item_id = None
            self._sync_item_selection_visual()
            return
        if items.highlighted_child is not None and isinstance(items.highlighted_child.name, str):
            self._last_item_id = items.highlighted_child.name
            self._sync_item_selection_visual()
            return
        names = [child.name for child in items.children]
        if isinstance(self._last_item_id, str) and self._last_item_id in names:
            items.index = names.index(self._last_item_id)
        else:
            items.index = 0
            if items.highlighted_child is not None:
                self._last_item_id = items.highlighted_child.name
        self._sync_item_selection_visual()

    def _sync_item_selection_visual(self) -> None:
        items = self.query_one("#item-list", ListView)
        selected_name = items.highlighted_child.name if items.highlighted_child is not None else None
        for child in items.children:
            child.remove_class("item-selected")
            if selected_name is not None and child.name == selected_name:
                child.add_class("item-selected")

    def _set_status(self, text: str) -> None:
        status = self.query_one("#item-status", Static)
        status.update(text)
        if text:
            status.add_class("show")
        else:
            status.remove_class("show")

    def _set_output(self, text: str) -> None:
        output = self.query_one("#item-output", Static)
        output.update(text)
        if text:
            output.add_class("show")
        else:
            output.remove_class("show")

    def _set_active_panel(self, active_list_id: str) -> None:
        item_panel = self.query_one("#item-list-panel", Vertical)
        action_panel = self.query_one("#item-actions-panel", Vertical)
        item_panel.remove_class("active-panel")
        action_panel.remove_class("active-panel")
        if active_list_id == "item-actions":
            action_panel.add_class("active-panel")
        else:
            item_panel.add_class("active-panel")

    def _execute_action(self, action_id: str, item_id: str | None) -> None:
        result = self.run_action(action_id, item_id)
        self.app.refresh(layout=True, repaint=True)
        self.refresh(layout=True, repaint=True)
        if result.refresh_items:
            preferred = result.preferred_item_id if result.preferred_item_id is not None else item_id
            self._refresh_items(preferred_item_id=preferred)
        self._ensure_item_selection()
        if result.focus_items:
            self.action_focus_items()
        if result.status is not None:
            self._set_status(result.status)
        elif result.rc == 0:
            suffix = item_id if item_id else "-"
            self._set_status(f"[ok] {action_id} {suffix}")
        else:
            suffix = item_id if item_id else "-"
            self._set_status(f"[error] {action_id} failed ({result.rc}) for {suffix}")
        self._set_output(result.output)

    def _run_action_by_id(self, action_id: str) -> None:
        action = self._action_defs.get(action_id)
        if action is None:
            return
        item_id = self._selected_item_id()
        if action.requires_item and item_id is None:
            self._set_status("[warn] No item selected")
            return
        confirm = self.confirm_action(action_id, item_id)
        if confirm is None:
            self._execute_action(action_id, item_id)
            return

        def _after_confirm(confirmed: bool | None) -> None:
            if confirmed:
                self._execute_action(action_id, item_id)
            # Always restore interaction state after modal dismissal.
            self.action_focus_items()
            self.app.refresh(layout=True, repaint=True)
            self.refresh(layout=True, repaint=True)

        self.app.push_screen(
            ConfirmModal(
                title=confirm.title,
                detail=confirm.detail,
                yes_label=confirm.yes_label,
                no_label=confirm.no_label,
                default_no=confirm.default_no,
            ),
            _after_confirm,
        )

    def _selected_action_id(self) -> str | None:
        actions = self.query_one("#item-actions", ListView)
        if actions.highlighted_child is not None and isinstance(actions.highlighted_child.name, str):
            return actions.highlighted_child.name
        default_action = self.get_default_action_id()
        if default_action is not None and default_action in self._action_defs:
            return default_action
        if actions.children and isinstance(actions.children[0].name, str):
            return actions.children[0].name
        return None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "item-actions" or event.item is None:
            return
        action_id = event.item.name or ""
        self._run_action_by_id(action_id)

    def on_list_view_highlighted(self, event) -> None:
        if event.list_view.id != "item-list":
            return
        self._ensure_item_selection()

    def on_descendant_focus(self, event) -> None:
        widget = getattr(event, "widget", None)
        widget_id = getattr(widget, "id", "")
        if widget_id in {"item-list", "item-actions"}:
            self._set_active_panel(widget_id)

    def action_focus_items(self) -> None:
        self.query_one("#item-list", ListView).focus()
        self._set_active_panel("item-list")

    def action_focus_actions(self) -> None:
        self.query_one("#item-actions", ListView).focus()
        self._set_active_panel("item-actions")

    def _page_move_list(self, list_view: ListView, down: bool) -> None:
        if not list_view.children:
            return
        row_count = len(list_view.children)
        current_index = max(0, min(row_count - 1, int(list_view.index or 0)))
        page_rows = max(1, int(list_view.size.height))
        top = max(0, int(list_view.scroll_y))
        offset = current_index - top
        if offset < 0:
            offset = 0
        if offset >= page_rows:
            offset = page_rows - 1
        if down:
            target_top = min(int(list_view.max_scroll_y), top + page_rows)
        else:
            target_top = max(0, top - page_rows)
        new_index = max(0, min(row_count - 1, target_top + offset))
        list_view.index = new_index
        list_view.scroll_to(y=target_top, animate=False, force=True)

    def on_key(self, event) -> None:
        if event.key == "enter":
            focused = self.app.focused
            focused_id = getattr(focused, "id", "")
            if focused_id == "item-list":
                action_id = self._selected_action_id()
                if action_id:
                    self._run_action_by_id(action_id)
                    event.stop()
                    event.prevent_default()
                return
        if event.key not in {"pageup", "pagedown"}:
            return
        focused = self.app.focused
        if not isinstance(focused, ListView):
            return
        self._page_move_list(focused, down=event.key == "pagedown")
        event.stop()
        event.prevent_default()

    def _run_shortcut_action(self, action_id: str) -> None:
        self._run_action_by_id(action_id)
