from __future__ import annotations

import io
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from cmds import deps as deps_cmd
from cmds import image as image_cmd
from mods.tui.screens.item_action_screen import ActionResult, ItemAction, ItemActionScreen
from mods.tui.screens.prompt_modal import PromptModal


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

    def get_items(self) -> list[tuple[str, Text]]:
        rows: list[tuple[str, Text]] = []
        dep_map, env = deps_cmd._deps_by_id()  # noqa: SLF001 - internal reuse within same project
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
            rows.append((dep_id, Text(f"{marker} {label}")))
        return rows

    def _run_capture(self, fn, *args) -> tuple[int, str]:
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(out):
            rc = int(fn(*args))
        return rc, out.getvalue().rstrip()

    def _dep_for_id(self, dep_id: str) -> tuple[dict | None, Path | None]:
        dep_map, env = deps_cmd._deps_by_id()  # noqa: SLF001 - internal reuse
        dep = dep_map.get(dep_id)
        if dep is None:
            return None, None
        return dep, deps_cmd.resolve_dep_path(env, dep["path"])

    def _artifact_paths(self, dep: dict, dep_path: Path) -> list[Path]:
        build = dep.get("build")
        if not isinstance(build, dict):
            return []
        artifacts = build.get("artifacts")
        if not isinstance(artifacts, list):
            return []
        paths: list[Path] = []
        for raw in artifacts:
            if not isinstance(raw, str) or not raw.strip():
                continue
            p = Path(raw)
            paths.append(p if p.is_absolute() else dep_path / p)
        return paths

    def _stage_artifacts(self, dep_id: str, target: str) -> ActionResult:
        dep, dep_path = self._dep_for_id(dep_id)
        if dep is None or dep_path is None:
            return ActionResult(rc=1, status=f"[error] Unknown dependency: {dep_id}")
        artifact_paths = self._artifact_paths(dep, dep_path)
        if not artifact_paths:
            return ActionResult(rc=1, status=f"[warn] No build.artifacts configured for {dep_id}")

        out = io.StringIO()
        failures = 0
        with redirect_stdout(out), redirect_stderr(out):
            for path in artifact_paths:
                image_cmd.copy_path_to_target(path, target)
                if not path.exists():
                    failures += 1
        output = out.getvalue().rstrip()
        if failures:
            return ActionResult(
                rc=1,
                output=output,
                status=f"[error] Staging had missing artifacts for {dep_id}",
                refresh_items=False,
                preferred_item_id=dep_id,
            )
        target_label = "romdisk" if target == "romdisk" else f"image {target}"
        return ActionResult(
            rc=0,
            output=output,
            status=f"[ok] staged artifacts for {dep_id} -> {target_label}",
            preferred_item_id=dep_id,
        )

    def _on_stage_target(self, dep_id: str, value: str | None) -> None:
        if value is None:
            self._set_status("")
            return
        target = value.strip().lower()
        if target.startswith("image "):
            target = target.split(" ", 1)[1].strip()
        if target in {"romdisk", "tf", "cf", "eeprom"}:
            self._pending_stage_target = target
            self._execute_action("stage", dep_id)
            return
        self._set_status("[warn] Target must be one of: romdisk, tf, cf, eeprom")

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        if action_id == "refresh":
            return ActionResult(status="[ok] refreshed", refresh_items=True, preferred_item_id=self._last_item_id)
        if item_id is None:
            return ActionResult(rc=1, status="[warn] No dependency selected")
        if action_id == "info":
            rc, output = self._run_capture(deps_cmd.subcmd_info, [item_id])
            if output:
                self.app.push_screen(DepsInfoModal(item_id, output))
            return ActionResult(rc=rc, output="")
        if action_id == "install":
            rc, output = self._run_capture(deps_cmd.subcmd_install, [item_id])
            return ActionResult(rc=rc, output=output, refresh_items=True, preferred_item_id=item_id)
        if action_id == "remove":
            rc, output = self._run_capture(deps_cmd.subcmd_remove, [item_id])
            return ActionResult(rc=rc, output=output, refresh_items=True, preferred_item_id=item_id)
        if action_id == "build":
            with self.app.suspend():
                rc = int(deps_cmd.subcmd_build([item_id]))
                try:
                    input("\nPress Enter to return to ZDE TUI...")
                except EOFError:
                    pass
            return ActionResult(rc=rc, refresh_items=True, preferred_item_id=item_id)
        if action_id == "stage":
            if self._pending_stage_target is None:
                self.app.push_screen(
                    PromptModal(
                        title="Stage Artifacts Target",
                        detail="Enter target: romdisk, tf, cf, or eeprom",
                        placeholder="romdisk",
                        submit_label="Stage",
                        cancel_label="Cancel",
                    ),
                    lambda value: self._on_stage_target(item_id, value),
                )
                return ActionResult(status="")
            target = self._pending_stage_target
            self._pending_stage_target = None
            return self._stage_artifacts(item_id, target)
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
