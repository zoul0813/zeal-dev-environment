from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen, Screen
from textual.widgets import Footer, Header, Label, ListItem, ListView, Static

from cmds import deps as deps_cmd


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


class DepsMenuScreen(Screen[None]):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("left", "focus_packages", "Packages"),
        ("right", "focus_actions", "Actions"),
        ("f3", "run_info", "Info"),
        ("f5", "run_install", "Install"),
        ("f6", "run_build", "Build"),
        ("f8", "run_remove", "Remove"),
        ("f2", "run_refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._last_dep_id: str | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Vertical(
            Static("Dependencies"),
            Static("Select a dependency, then choose an action"),
            Horizontal(
                Vertical(
                    Static("Packages"),
                    ListView(id="deps-list"),
                    id="deps-list-panel",
                ),
                Vertical(
                    Static("Actions"),
                    ListView(id="deps-actions"),
                    id="deps-actions-panel",
                ),
                id="deps-layout",
            ),
            Static("", id="deps-status", classes="status-line"),
            Static("", id="deps-output", classes="status-line"),
            classes="main-body",
        )
        yield Static("", id="cwd-bar")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_deps()
        actions = self.query_one("#deps-actions", ListView)
        actions.append(ListItem(Label("info"), name="info"))
        actions.append(ListItem(Label("install"), name="install"))
        actions.append(ListItem(Label("build"), name="build"))
        actions.append(ListItem(Label("remove"), name="remove"))
        actions.append(ListItem(Label("refresh"), name="refresh"))
        actions.index = 0
        self.query_one("#deps-list", ListView).focus()
        self._set_active_panel("deps-list")

    def _set_active_panel(self, active_list_id: str) -> None:
        list_panel = self.query_one("#deps-list-panel", Vertical)
        actions_panel = self.query_one("#deps-actions-panel", Vertical)
        list_panel.remove_class("active-panel")
        actions_panel.remove_class("active-panel")
        if active_list_id == "deps-actions":
            actions_panel.add_class("active-panel")
            return
        list_panel.add_class("active-panel")

    def _refresh_deps(self, preferred_dep_id: str | None = None) -> None:
        deps_list = self.query_one("#deps-list", ListView)
        clear_fn = getattr(deps_list, "clear", None)
        if callable(clear_fn):
            clear_fn()
        else:
            while deps_list.children:
                deps_list.remove(deps_list.children[0])
        dep_map, env = deps_cmd._deps_by_id()  # noqa: SLF001 - internal reuse within same project
        lock = deps_cmd.load_lock(env.lock_file)
        tracked = lock.get("dependencies", {})
        if not isinstance(tracked, dict):
            tracked = {}

        dep_ids = sorted(dep_map.keys())
        for dep_id in dep_ids:
            dep = dep_map[dep_id]
            dep_path = deps_cmd.resolve_dep_path(env, dep["path"])
            installed = deps_cmd.is_git_repo(dep_path)
            metadata = dep.get("metadata", {})
            display_name = ""
            if isinstance(metadata, dict):
                raw_name = metadata.get("name")
                if isinstance(raw_name, str):
                    display_name = raw_name.strip()
            label = f"{display_name} ({dep_id})" if display_name else dep_id
            marker = "[x]" if installed else "[ ]"
            deps_list.append(ListItem(Label(Text(f"{marker} {label}")), name=dep_id))

        if not deps_list.children:
            self._last_dep_id = None
            return
        wanted = preferred_dep_id or self._last_dep_id
        if wanted and wanted in dep_ids:
            deps_list.index = dep_ids.index(wanted)
            self._last_dep_id = wanted
            return
        deps_list.index = 0
        if deps_list.highlighted_child is not None:
            self._last_dep_id = deps_list.highlighted_child.name

    def _selected_dep_id(self) -> str | None:
        deps_list = self.query_one("#deps-list", ListView)
        if deps_list.highlighted_child is None:
            return self._last_dep_id
        selected = deps_list.highlighted_child.name
        if isinstance(selected, str):
            self._last_dep_id = selected
        return selected

    def _ensure_dep_selection(self) -> None:
        deps_list = self.query_one("#deps-list", ListView)
        if not deps_list.children:
            self._last_dep_id = None
            self._sync_dep_selection_visual()
            return
        if deps_list.highlighted_child is not None:
            selected = deps_list.highlighted_child.name
            if isinstance(selected, str):
                self._last_dep_id = selected
            self._sync_dep_selection_visual()
            return
        dep_ids = [child.name for child in deps_list.children]
        wanted = self._last_dep_id
        if isinstance(wanted, str) and wanted in dep_ids:
            deps_list.index = dep_ids.index(wanted)
            self._sync_dep_selection_visual()
            return
        deps_list.index = 0
        if deps_list.highlighted_child is not None:
            self._last_dep_id = deps_list.highlighted_child.name
        self._sync_dep_selection_visual()

    def _sync_dep_selection_visual(self) -> None:
        deps_list = self.query_one("#deps-list", ListView)
        selected_name = None
        if deps_list.highlighted_child is not None:
            selected_name = deps_list.highlighted_child.name
        for child in deps_list.children:
            child.remove_class("deps-selected")
            if selected_name is not None and child.name == selected_name:
                child.add_class("deps-selected")

    def _set_status(self, text: str) -> None:
        status = self.query_one("#deps-status", Static)
        status.update(text)
        if text:
            status.add_class("show")
        else:
            status.remove_class("show")

    def _set_output(self, text: str) -> None:
        output = self.query_one("#deps-output", Static)
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

    def _run_action(self, action_id: str, dep_id: str) -> None:
        self._last_dep_id = dep_id
        if action_id == "info":
            rc, output = self._run_capture(deps_cmd.subcmd_info, [dep_id])
        elif action_id == "install":
            rc, output = self._run_capture(deps_cmd.subcmd_install, [dep_id])
        elif action_id == "remove":
            rc, output = self._run_capture(deps_cmd.subcmd_remove, [dep_id])
        elif action_id == "build":
            with self.app.suspend():
                rc = int(deps_cmd.subcmd_build([dep_id]))
                try:
                    input("\nPress Enter to return to ZDE TUI...")
                except EOFError:
                    pass
            output = ""
        else:
            rc, output = 0, ""

        self.app.refresh(layout=True, repaint=True)
        self.refresh(layout=True, repaint=True)
        if action_id in {"install", "remove", "build", "refresh"}:
            self._refresh_deps(preferred_dep_id=dep_id if dep_id != "-" else None)
        self._ensure_dep_selection()
        self.query_one("#deps-list", ListView).focus()
        self._set_active_panel("deps-list")
        if rc == 0:
            self._set_status(f"[ok] {action_id} {dep_id}")
        else:
            self._set_status(f"[error] {action_id} failed ({rc}) for {dep_id}")
        if action_id == "info" and output:
            self.app.push_screen(DepsInfoModal(dep_id, output))
            self._set_output("")
            return
        self._set_output(output)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id != "deps-actions" or event.item is None:
            return
        action_id = event.item.name or ""
        if action_id == "refresh":
            self._run_action("refresh", "-")
            return
        dep_id = self._selected_dep_id()
        if dep_id is None:
            self._set_status("[warn] No dependency selected")
            return
        self._run_action(action_id, dep_id)

    def on_list_view_highlighted(self, event) -> None:
        if event.list_view.id != "deps-list":
            return
        self._ensure_dep_selection()

    def on_descendant_focus(self, event) -> None:
        widget = getattr(event, "widget", None)
        widget_id = getattr(widget, "id", "")
        if widget_id in {"deps-list", "deps-actions"}:
            self._set_active_panel(widget_id)

    def action_focus_packages(self) -> None:
        self.query_one("#deps-list", ListView).focus()
        self._set_active_panel("deps-list")

    def action_focus_actions(self) -> None:
        self.query_one("#deps-actions", ListView).focus()
        self._set_active_panel("deps-actions")

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

    def _run_shortcut_action(self, action_id: str) -> None:
        if action_id == "refresh":
            self._run_action("refresh", "-")
            return
        dep_id = self._selected_dep_id()
        if dep_id is None:
            self._set_status("[warn] No dependency selected")
            return
        self._run_action(action_id, dep_id)

    def action_run_info(self) -> None:
        self._run_shortcut_action("info")

    def action_run_install(self) -> None:
        self._run_shortcut_action("install")

    def action_run_build(self) -> None:
        self._run_shortcut_action("build")

    def action_run_remove(self) -> None:
        self._run_shortcut_action("remove")

    def action_run_refresh(self) -> None:
        self._run_shortcut_action("refresh")
