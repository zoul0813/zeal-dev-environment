from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from cmds import romdisk as romdisk_cmd
from mods.tui.screens.confirm_modal import ConfirmModal


class RomdiskMenuScreen(Screen[None]):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("left", "focus_entries", "Entries"),
        ("right", "focus_actions", "Actions"),
        ("f8", "run_remove", "Remove"),
        ("f2", "run_refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._last_name: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("Romdisk"),
            Static("Select a romdisk entry, then choose an action"),
            Horizontal(
                Vertical(
                    Static("Entries"),
                    ListView(id="romdisk-entries"),
                    id="romdisk-entries-panel",
                ),
                Vertical(
                    Static("Actions"),
                    ListView(id="romdisk-actions"),
                    id="romdisk-actions-panel",
                ),
                id="romdisk-layout",
            ),
            Static("", id="romdisk-status", classes="status-line"),
            Static("", id="romdisk-output", classes="status-line"),
            classes="main-body",
        )
        yield Static("", id="cwd-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_entries()
        actions = self.query_one("#romdisk-actions", ListView)
        actions.append(ListItem(Label("remove"), name="remove"))
        actions.append(ListItem(Label("refresh"), name="refresh"))
        actions.index = 0
        self.query_one("#romdisk-entries", ListView).focus()
        self._set_active_panel("romdisk-entries")

    def _set_active_panel(self, active_list_id: str) -> None:
        entries_panel = self.query_one("#romdisk-entries-panel", Vertical)
        actions_panel = self.query_one("#romdisk-actions-panel", Vertical)
        entries_panel.remove_class("active-panel")
        actions_panel.remove_class("active-panel")
        if active_list_id == "romdisk-actions":
            actions_panel.add_class("active-panel")
            return
        entries_panel.add_class("active-panel")

    def _refresh_entries(self, preferred_name: str | None = None) -> None:
        entries = self.query_one("#romdisk-entries", ListView)
        clear_fn = getattr(entries, "clear", None)
        if callable(clear_fn):
            clear_fn()
        else:
            while entries.children:
                entries.remove(entries.children[0])

        rows = romdisk_cmd._romdisk_rows()  # noqa: SLF001 - shared formatter
        for name, line in rows:
            entries.append(ListItem(Label(line), name=name))

        if not entries.children:
            self._last_name = None
            return

        names = [name for name, _ in rows]
        wanted = preferred_name or self._last_name
        if wanted and wanted in names:
            entries.index = names.index(wanted)
            self._last_name = wanted
            return
        entries.index = 0
        if entries.highlighted_child is not None:
            self._last_name = entries.highlighted_child.name

    def _selected_name(self) -> str | None:
        entries = self.query_one("#romdisk-entries", ListView)
        if entries.highlighted_child is None:
            return self._last_name
        name = entries.highlighted_child.name
        if isinstance(name, str):
            self._last_name = name
        return name

    def _set_status(self, text: str) -> None:
        status = self.query_one("#romdisk-status", Static)
        status.update(text)
        if text:
            status.add_class("show")
        else:
            status.remove_class("show")

    def _set_output(self, text: str) -> None:
        output = self.query_one("#romdisk-output", Static)
        output.update(text)
        if text:
            output.add_class("show")
        else:
            output.remove_class("show")

    def _run_capture(self, fn, *args) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = int(fn(*args))
        return rc, out.getvalue().rstrip()

    def _run_remove(self, name: str) -> None:
        rc, output = self._run_capture(romdisk_cmd.subcmd_rm, [name])
        self._refresh_entries(preferred_name=name)
        self.query_one("#romdisk-entries", ListView).focus()
        self._set_active_panel("romdisk-entries")
        if rc == 0:
            self._set_status(f"[ok] removed {name}")
        else:
            self._set_status(f"[error] remove failed ({rc}) for {name}")
        self._set_output(output)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "romdisk-actions" or event.item is None:
            return
        action = event.item.name or ""
        if action == "refresh":
            self._refresh_entries()
            self.query_one("#romdisk-entries", ListView).focus()
            self._set_active_panel("romdisk-entries")
            self._set_status("[ok] refreshed")
            self._set_output("")
            return
        if action != "remove":
            return
        name = self._selected_name()
        if name is None:
            self._set_status("[warn] No romdisk entry selected")
            return
        self.app.push_screen(
            ConfirmModal(
                title=f"Remove '{name}'?",
                detail="Press Y to remove, N/Esc to cancel.",
                yes_label="Remove",
                no_label="Cancel",
                default_no=True,
            ),
            lambda yes: self._run_remove(name) if yes else None,
        )

    def on_descendant_focus(self, event) -> None:
        widget = getattr(event, "widget", None)
        widget_id = getattr(widget, "id", "")
        if widget_id in {"romdisk-entries", "romdisk-actions"}:
            self._set_active_panel(widget_id)

    def action_focus_entries(self) -> None:
        self.query_one("#romdisk-entries", ListView).focus()
        self._set_active_panel("romdisk-entries")

    def action_focus_actions(self) -> None:
        self.query_one("#romdisk-actions", ListView).focus()
        self._set_active_panel("romdisk-actions")

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
        if event.key not in {"pageup", "pagedown"}:
            return
        focused = self.app.focused
        if not isinstance(focused, ListView):
            return
        self._page_move_list(focused, down=event.key == "pagedown")
        event.stop()
        event.prevent_default()

    def action_run_refresh(self) -> None:
        self._refresh_entries()
        self.query_one("#romdisk-entries", ListView).focus()
        self._set_active_panel("romdisk-entries")
        self._set_status("[ok] refreshed")
        self._set_output("")

    def action_run_remove(self) -> None:
        name = self._selected_name()
        if name is None:
            self._set_status("[warn] No romdisk entry selected")
            return
        self.app.push_screen(
            ConfirmModal(
                title=f"Remove '{name}'?",
                detail="Press Y to remove, N/Esc to cancel.",
                yes_label="Remove",
                no_label="Cancel",
                default_no=True,
            ),
            lambda yes: self._run_remove(name) if yes else None,
        )
