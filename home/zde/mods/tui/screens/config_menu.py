from __future__ import annotations

from rich.text import Text

from mods.config import Config, ConfigOption
from mods.tui.screens.choice_modal import ChoiceModal
from mods.tui.screens.item_action_screen import ActionResult, ItemAction, ItemActionScreen
from mods.tui.screens.prompt_modal import PromptModal


class ConfigMenuScreen(ItemActionScreen):
    BINDINGS = [
        ("escape", "app.pop_screen", "Back"),
        ("left", "focus_items", "Keys"),
        ("right", "focus_actions", "Actions"),
        ("f4", "run_edit", "Edit"),
        ("f6", "run_toggle", "Toggle"),
        ("f8", "run_unset", "Unset"),
        ("f2", "run_refresh", "Refresh"),
    ]

    def __init__(self) -> None:
        super().__init__(
            title="Configuration",
            subtitle="Select a config key, then choose an action",
            items_title="Keys",
            actions_title="Actions",
        )

    def get_actions(self) -> list[ItemAction]:
        return [
            ItemAction("edit", "edit"),
            ItemAction("toggle", "toggle"),
            ItemAction("unset", "unset"),
            ItemAction("refresh", "refresh", requires_item=False),
        ]

    def get_default_action_id(self) -> str | None:
        return "edit"

    def is_action_visible(self, action_id: str, item_id: str | None) -> bool:
        if action_id == "refresh":
            return True
        if not isinstance(item_id, str):
            return False
        option = Config.resolve_option(item_id)
        if option is None:
            return False
        if action_id == "toggle":
            return option.value_type == "bool"
        if action_id == "unset":
            cfg = Config.load()
            return cfg.is_explicit(option.key)
        return True

    def get_items(self) -> list[tuple[str, Text]]:
        rows: list[tuple[str, Text]] = []
        cfg = Config.load()
        for option in Config.iter_options():
            value, explicit = cfg.get_with_source(option.key)
            line = Text()
            line.append(option.key, style="bold")
            line.append(" = ")

            rendered = _format_option_value(option, value)
            if not explicit:
                line.append(rendered, style="white")
                line.append(" [default]", style="dim")
            elif option.value_type == "bool":
                line.append(rendered, style="green" if bool(value) else "yellow")
                line.append(" [explicit]", style="dim")
            else:
                line.append(rendered, style="green")
                line.append(" [explicit]", style="dim")

            line.append(f" - {option.description}", style="dim")
            rows.append((option.key, line))
        return rows

    def run_action(self, action_id: str, item_id: str | None) -> ActionResult:
        if action_id == "refresh":
            return ActionResult(status="[ok] refreshed", refresh_items=True, preferred_item_id=self._last_item_id)

        if not isinstance(item_id, str):
            return ActionResult(rc=1, status="[warn] No config key selected")

        option = Config.resolve_option(item_id)
        if option is None:
            return ActionResult(rc=1, status=f"[error] Unknown config key: {item_id}")

        if action_id == "unset":
            cfg = Config.load()
            cfg.unset(option.key)
            cfg.save()
            return ActionResult(
                rc=0,
                status=f"[ok] unset {option.key}",
                refresh_items=True,
                preferred_item_id=item_id,
            )

        if action_id == "toggle":
            if option.value_type != "bool":
                return ActionResult(rc=1, status=f"[warn] {option.key} is not a boolean key")
            cfg = Config.load()
            current = bool(cfg.get(option.key))
            cfg.set(option.key, not current)
            cfg.save()
            state = "on" if not current else "off"
            return ActionResult(
                rc=0,
                status=f"[ok] {option.key}: {state}",
                refresh_items=True,
                preferred_item_id=item_id,
            )

        if action_id == "edit":
            self._open_editor(option)
            return ActionResult(status="")

        return ActionResult(rc=0)

    def _open_editor(self, option: ConfigOption) -> None:
        cfg = Config.load()
        current = cfg.get(option.key)
        if option.value_type == "bool":
            current_text = "on" if bool(current) else "off"
            self.app.push_screen(
                ChoiceModal(
                    title=f"Set {option.key}",
                    detail=f"{option.description} (current: {current_text})",
                    options=[("on", "on"), ("off", "off")],
                ),
                lambda value: self._on_bool_selected(option, value),
            )
            return

        current_text = str(current)
        self.app.push_screen(
            PromptModal(
                title=f"Set {option.key}",
                detail=option.description,
                placeholder=current_text,
                initial_value=current_text,
                submit_label="Save",
                cancel_label="Cancel",
                empty_allowed=False,
            ),
            lambda value: self._on_text_submitted(option, value),
        )

    def _on_bool_selected(self, option: ConfigOption, raw: str | None) -> None:
        if raw is None:
            self._after_modal(status="", preferred_key=option.key)
            return
        parsed = Config.parse_bool(raw)
        if parsed is None:
            self._after_modal(status=f"[error] Invalid value for {option.key}: {raw}", preferred_key=option.key)
            return
        cfg = Config.load()
        cfg.set(option.key, parsed)
        cfg.save()
        state = "on" if parsed else "off"
        self._after_modal(status=f"[ok] {option.key}: {state}", preferred_key=option.key)

    def _on_text_submitted(self, option: ConfigOption, raw: str | None) -> None:
        if raw is None:
            self._after_modal(status="", preferred_key=option.key)
            return
        cfg = Config.load()
        try:
            value = cfg.set(option.key, raw)
        except ValueError as exc:
            self._after_modal(status=f"[error] {exc}", preferred_key=option.key)
            return
        cfg.save()
        self._after_modal(status=f"[ok] {option.key}: {value}", preferred_key=option.key)

    def _after_modal(self, *, status: str, preferred_key: str | None) -> None:
        self._refresh_items(preferred_item_id=preferred_key)
        self._ensure_item_selection()
        self._refresh_actions()
        self.action_focus_items()
        self._set_status(status)
        self._set_output("")
        self.app.refresh(layout=True, repaint=True)
        self.refresh(layout=True, repaint=True)

    def action_run_edit(self) -> None:
        self._run_shortcut_action("edit")

    def action_run_toggle(self) -> None:
        self._run_shortcut_action("toggle")

    def action_run_unset(self) -> None:
        self._run_shortcut_action("unset")

    def action_run_refresh(self) -> None:
        self._run_shortcut_action("refresh")


def _format_option_value(option: ConfigOption, value: object) -> str:
    if option.value_type == "bool":
        return "on" if bool(value) else "off"
    return str(value)
