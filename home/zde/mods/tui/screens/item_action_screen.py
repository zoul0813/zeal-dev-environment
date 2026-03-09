from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from mods.tui.exec import pause_after_run, suspend_for_external_output
from mods.tui.screens.confirm_modal import ConfirmModal

try:
    from textual.binding import Binding
except Exception:  # pragma: no cover - compatibility fallback for older Textual
    Binding = None


@dataclass(frozen=True)
class ItemAction:
    id: str
    label: str
    requires_item: bool = True
    shortcut: str = ""
    pause_after_run: bool = False
    callback: Callable[["ItemEntry"], ActionResult | int | None] | None = None


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


@dataclass
class ItemEntry:
    id: str
    label: Any
    action_ids: list[str] = field(default_factory=list)
    data: Any = None


@dataclass
class GroupEntry:
    label: str
    items: list[ItemEntry]


class ItemActionScreen(Screen[None]):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("left", "focus_items", "Items"),
        ("right", "focus_actions", "Actions"),
    ]
    REFRESH_ACTION = True
    DEFAULT_ACTION_ID: str | None = None

    _GROUP_NAME_PREFIX = "__group__:"

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
        self._all_actions: list[ItemAction] = []
        self._action_defs: dict[str, ItemAction] = {}
        self._visible_action_ids: list[str] = []
        self._item_entries_by_id: dict[str, ItemEntry] = {}
        self._base_bindings = None
        self._dynamic_shortcuts_enabled: bool = False

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
        self._all_actions = list(self.get_actions())
        if self.REFRESH_ACTION and all(action.id != "refresh" for action in self._all_actions):
            self._all_actions.append(ItemAction("refresh", "refresh", requires_item=False, shortcut="f2"))
        self._action_defs = {action.id: action for action in self._all_actions}
        bindings = getattr(self, "_bindings", None)
        copy_fn = getattr(bindings, "copy", None)
        if callable(copy_fn):
            self._base_bindings = copy_fn()
        self._refresh_items()
        self._refresh_actions()
        self._sync_footer_shortcuts()
        self.action_focus_items()

    def get_items(self) -> list[ItemEntry | GroupEntry]:
        raise NotImplementedError

    def get_actions(self) -> list[ItemAction]:
        raise NotImplementedError

    def confirm_action(self, action_id: str, item_id: str | None) -> ConfirmRequest | None:
        return None

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        if action_id == "refresh":
            return ActionResult(status="[ok] refreshed", refresh_items=True, preferred_item_id=self._last_item_id)
        if item_id is None:
            return ActionResult(rc=1, status="[warn] No item selected")
        item = self._item_entries_by_id.get(item_id)
        if item is None:
            return ActionResult(rc=0)
        if item.action_ids and action_id not in item.action_ids:
            return ActionResult(rc=0)
        action = self._action_defs.get(action_id)
        handler = action.callback if isinstance(action, ItemAction) else None
        if not callable(handler):
            return ActionResult(rc=0)
        try:
            raw = handler(item)
        except Exception as exc:
            return ActionResult(rc=1, status=f"[error] {action_id} failed: {exc}")
        if isinstance(raw, ActionResult):
            return raw
        if isinstance(raw, int):
            return ActionResult(rc=int(raw))
        return ActionResult(rc=0)

    def get_default_action_id(self) -> str | None:
        return self.DEFAULT_ACTION_ID

    def is_action_visible(self, action_id: str, item_id: str | None) -> bool:
        action = self._action_defs.get(action_id)
        if isinstance(action, ItemAction) and not action.requires_item:
            return True
        if item_id is not None:
            item = self._item_entries_by_id.get(item_id)
            if item is not None and item.action_ids:
                return action_id in item.action_ids
        return True

    def preferred_action_id(self, item_id: str | None) -> str | None:
        return self.get_default_action_id()

    def _is_group_heading_name(self, name: object) -> bool:
        return isinstance(name, str) and name.startswith(self._GROUP_NAME_PREFIX)

    def _is_selectable_item(self, item: ListItem | None) -> bool:
        if item is None:
            return False
        name = item.name
        return isinstance(name, str) and not self._is_group_heading_name(name)

    def _find_item_index(self, item_id: str) -> int | None:
        items = self.query_one("#item-list", ListView)
        for index, child in enumerate(items.children):
            if child.name == item_id:
                return index
        return None

    def _first_selectable_index(self) -> int | None:
        items = self.query_one("#item-list", ListView)
        for index, child in enumerate(items.children):
            if self._is_selectable_item(child):
                return index
        return None

    def _nearest_selectable_index_from(self, start_index: int, prefer_down: bool) -> int | None:
        items = self.query_one("#item-list", ListView)
        row_count = len(items.children)
        if row_count <= 0:
            return None

        def scan(direction: int) -> int | None:
            idx = start_index
            while 0 <= idx < row_count:
                child = items.children[idx]
                if self._is_selectable_item(child):
                    return idx
                idx += direction
            return None

        primary = scan(1 if prefer_down else -1)
        if primary is not None:
            return primary
        return scan(-1 if prefer_down else 1)

    def _refresh_items(self, preferred_item_id: str | None = None) -> None:
        items = self.query_one("#item-list", ListView)
        clear_fn = getattr(items, "clear", None)
        if callable(clear_fn):
            clear_fn()
        else:
            while items.children:
                items.remove(items.children[0])

        names: list[str] = []
        self._item_entries_by_id = {}
        rows = self.get_items()
        group_index = 0
        for row in rows:
            if isinstance(row, GroupEntry):
                group_label = row.label
                group_rows = row.items
                if not group_rows:
                    continue
                heading = ListItem(Label(str(group_label)), name=f"{self._GROUP_NAME_PREFIX}{group_index}")
                heading.add_class("item-group-heading")
                items.append(heading)
                group_index += 1
                for group_row in group_rows:
                    self._item_entries_by_id[group_row.id] = group_row
                    names.append(group_row.id)
                    items.append(ListItem(Label(group_row.label), name=group_row.id))
                continue
            self._item_entries_by_id[row.id] = row
            names.append(row.id)
            items.append(ListItem(Label(row.label), name=row.id))

        if not items.children or not names:
            self._last_item_id = None
            self._sync_item_selection_visual()
            return

        wanted = preferred_item_id or self._last_item_id
        target_index: int | None = None
        if wanted and wanted in names:
            target_index = self._find_item_index(wanted)
        if target_index is None:
            target_index = self._first_selectable_index()
        if target_index is not None:
            items.index = target_index
            if self._is_selectable_item(items.highlighted_child):
                selected = items.highlighted_child.name
                if isinstance(selected, str):
                    self._last_item_id = selected
        else:
            self._last_item_id = None
        self._sync_item_selection_visual()

    def _selected_item_id(self) -> str | None:
        items = self.query_one("#item-list", ListView)
        highlighted = items.highlighted_child
        if highlighted is None:
            if isinstance(self._last_item_id, str) and self._find_item_index(self._last_item_id) is not None:
                return self._last_item_id
            return None
        if self._is_selectable_item(highlighted):
            selected = highlighted.name
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
        first_index = self._first_selectable_index()
        if first_index is None:
            self._last_item_id = None
            self._sync_item_selection_visual()
            return
        if self._is_selectable_item(items.highlighted_child):
            selected = items.highlighted_child.name
            if isinstance(selected, str):
                self._last_item_id = selected
            self._sync_item_selection_visual()
            return
        current_index = max(0, min(len(items.children) - 1, int(items.index or 0)))
        last_index: int | None = None
        if isinstance(self._last_item_id, str):
            last_index = self._find_item_index(self._last_item_id)
        prefer_down = True
        if last_index is not None:
            prefer_down = current_index >= last_index
        target_index = self._nearest_selectable_index_from(current_index, prefer_down=prefer_down)
        if target_index is None:
            target_index = first_index
        items.index = target_index
        highlighted = items.highlighted_child
        if self._is_selectable_item(highlighted):
            selected = highlighted.name
            if isinstance(selected, str):
                self._last_item_id = selected
        else:
            self._last_item_id = None
        self._sync_item_selection_visual()

    def _sync_item_selection_visual(self) -> None:
        items = self.query_one("#item-list", ListView)
        selected_name: str | None = None
        if self._is_selectable_item(items.highlighted_child):
            name = items.highlighted_child.name
            if isinstance(name, str):
                selected_name = name
        for child in items.children:
            child.remove_class("item-selected")
            if selected_name is not None and self._is_selectable_item(child) and child.name == selected_name:
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

    def _refresh_actions(self, preferred_action_id: str | None = None) -> None:
        actions_view = self.query_one("#item-actions", ListView)
        selected_item_id = self._selected_item_id()
        previously_selected = self._selected_action_id()
        visible_actions = [a for a in self._all_actions if self.is_action_visible(a.id, selected_item_id)]
        self._visible_action_ids = [a.id for a in visible_actions]

        clear_fn = getattr(actions_view, "clear", None)
        if callable(clear_fn):
            clear_fn()
        else:
            while actions_view.children:
                actions_view.remove(actions_view.children[0])

        for action in visible_actions:
            actions_view.append(ListItem(Label(action.label), name=action.id))

        if not actions_view.children:
            self._sync_action_selection_visual()
            self._sync_footer_shortcuts()
            return

        wanted = preferred_action_id or self.preferred_action_id(selected_item_id) or previously_selected
        if isinstance(wanted, str) and wanted in self._visible_action_ids:
            actions_view.index = self._visible_action_ids.index(wanted)
            self._sync_action_selection_visual()
            self._sync_footer_shortcuts()
            return
        actions_view.index = 0
        self._sync_action_selection_visual()
        self._sync_footer_shortcuts()

    def _sync_action_selection_visual(self) -> None:
        actions = self.query_one("#item-actions", ListView)
        selected_name = actions.highlighted_child.name if actions.highlighted_child is not None else None
        for child in actions.children:
            child.remove_class("action-selected")
            if selected_name is not None and child.name == selected_name:
                child.add_class("action-selected")

    def _execute_action(self, action_id: str, item_id: str | None) -> None:
        selected_action = self._selected_action_id()
        action = self._action_defs.get(action_id)
        result = self.run_action(action_id, item_id)
        if isinstance(action, ItemAction) and action.pause_after_run:
            self._pause_after_run()
        self.app.refresh(layout=True, repaint=True)
        self.refresh(layout=True, repaint=True)
        if result.refresh_items:
            preferred = result.preferred_item_id if result.preferred_item_id is not None else item_id
            self._refresh_items(preferred_item_id=preferred)
        self._ensure_item_selection()
        self._refresh_actions(preferred_action_id=selected_action)
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

    def _pause_after_run(self) -> None:
        with suspend_for_external_output(self.app):
            pause_after_run()

    def _run_action_by_id(self, action_id: str) -> None:
        if self._visible_action_ids and action_id not in self._visible_action_ids:
            self._set_status(f"[warn] Action not available: {action_id}")
            return
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
        preferred = self.preferred_action_id(self._selected_item_id())
        if preferred is not None and preferred in self._visible_action_ids:
            return preferred
        if actions.children and isinstance(actions.children[0].name, str):
            return actions.children[0].name
        return None

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "item-actions" or event.item is None:
            return
        action_id = event.item.name or ""
        self._run_action_by_id(action_id)

    def on_list_view_highlighted(self, event) -> None:
        if event.list_view.id == "item-list":
            self._ensure_item_selection()
            self._refresh_actions()
            return
        if event.list_view.id == "item-actions":
            self._sync_action_selection_visual()

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
        if not self._dynamic_shortcuts_enabled:
            shortcut_action = self._shortcut_action_for_key(event.key)
            if isinstance(shortcut_action, str):
                self._run_shortcut_action(shortcut_action)
                event.stop()
                event.prevent_default()
                return
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

    def action_shortcut(self, action_id: str) -> None:
        if action_id == "refresh" and not self.REFRESH_ACTION:
            return
        self._run_shortcut_action(action_id)

    def _shortcut_action_for_key(self, key: str) -> str | None:
        token = key.strip().lower()
        if not token:
            return None
        item_id = self._selected_item_id()
        entry = self._item_entries_by_id.get(item_id) if isinstance(item_id, str) else None
        for action in self._all_actions:
            key_name = action.shortcut.strip().lower()
            target = action.id.strip()
            if not key_name or not target:
                continue
            if key_name != token:
                continue
            if entry is not None and (target in entry.action_ids or self.is_action_visible(target, entry.id)):
                return target
            if action.requires_item:
                continue
            return target
        return None

    def _sync_footer_shortcuts(self) -> None:
        base_copy = getattr(self._base_bindings, "copy", None)
        if not callable(base_copy):
            self._dynamic_shortcuts_enabled = False
            return

        dynamic_bindings = base_copy()
        bind_fn = getattr(dynamic_bindings, "bind", None)
        if not callable(bind_fn):
            self._dynamic_shortcuts_enabled = False
            return

        visible = set(self._visible_action_ids)
        for action in self._all_actions:
            if action.id not in visible:
                continue
            key_name = action.shortcut.strip().lower()
            if not key_name:
                continue
            label = action.label.strip() if isinstance(action.label, str) else action.id
            if not label:
                label = action.id
            try:
                if Binding is not None:
                    bind_fn(
                        Binding(
                            key=key_name,
                            action=f"shortcut('{action.id}')",
                            description=label,
                            show=True,
                            priority=True,
                        )
                    )
                else:
                    bind_fn(key_name, f"shortcut('{action.id}')", label, show=True, priority=True)
            except TypeError:
                try:
                    bind_fn(key_name, f"shortcut('{action.id}')", label, True, None, True)
                except TypeError:
                    try:
                        bind_fn(key_name, f"shortcut('{action.id}')", label)
                    except Exception:
                        continue
                except Exception:
                    continue
            except Exception:
                continue

        self._bindings = dynamic_bindings

        self._dynamic_shortcuts_enabled = True
        screen_refresh = getattr(self, "refresh_bindings", None)
        if callable(screen_refresh):
            try:
                screen_refresh()
            except Exception:
                pass
        app_refresh = getattr(self.app, "refresh_bindings", None)
        if callable(app_refresh):
            try:
                app_refresh()
            except Exception:
                pass
