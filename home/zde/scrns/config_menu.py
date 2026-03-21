from __future__ import annotations

from rich.text import Text

from mods.config import Config, ConfigOption
from mods.tui.modals.choice_modal import ChoiceModal
from mods.tui.panels.item_action_screen import ActionResult, GroupEntry, ItemAction, ItemActionScreen, ItemEntry
from mods.tui.modals.prompt_modal import PromptModal


class ConfigMenuScreen(ItemActionScreen):
    DEFAULT_ACTION_ID = "edit"

    def __init__(self) -> None:
        super().__init__(
            title="Configuration",
            subtitle="Select a config key, then choose an action",
            items_title="Keys",
            actions_title="Actions",
        )

    def get_actions(self) -> list[ItemAction]:
        return [
            ItemAction("edit", "edit", shortcut="f4", callback=self._action_edit),
            ItemAction("toggle", "toggle", shortcut="f6", callback=self._action_toggle),
            ItemAction("unset", "unset", shortcut="f8", callback=self._action_unset),
        ]

    def get_items(self) -> list[GroupEntry]:
        grouped: dict[str, list[ItemEntry]] = {}
        cfg = Config.load()
        for option in Config.iter_options():
            value, explicit = cfg.get_with_source(option.key)
            group, leaf = _split_option_key(option.key)
            line = Text()
            line.append(f"  {leaf}", style="bold")
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
            action_ids = ["edit"]
            if option.value_type == "bool":
                action_ids.append("toggle")
            if explicit:
                action_ids.append("unset")
            grouped.setdefault(group, []).append(
                ItemEntry(
                    id=option.key,
                    label=line,
                    action_ids=action_ids,
                    data=option,
                )
            )

        rows: list[GroupEntry] = []
        for group in sorted(grouped.keys()):
            rows.append(GroupEntry(label=_format_group_label(group), items=grouped[group]))
        return rows

    def _action_unset(self, item: ItemEntry) -> ActionResult:
        option = _option_from_item(item)
        cfg = Config.load()
        cfg.unset(option.key)
        cfg.save()
        return ActionResult(
            rc=0,
            status=f"[ok] unset {option.key}",
            refresh_items=True,
            preferred_item_id=option.key,
        )

    def _action_toggle(self, item: ItemEntry) -> ActionResult:
        option = _option_from_item(item)
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
            preferred_item_id=option.key,
        )

    def _action_edit(self, item: ItemEntry) -> ActionResult:
        option = _option_from_item(item)
        self._open_editor(option)
        return ActionResult(status="")

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
            value = cfg.set_from_text(option.key, raw)
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

def _format_option_value(option: ConfigOption, value: object) -> str:
    if option.value_type == "bool":
        return "on" if bool(value) else "off"
    return str(value)


def _split_option_key(key: str) -> tuple[str, str]:
    if "." not in key:
        return key, key
    group, leaf = key.split(".", 1)
    return group, leaf


def _format_group_label(group: str) -> str:
    text = group.replace("-", " ").replace("_", " ").strip()
    return text.title() if text else group


def _option_from_item(item: ItemEntry) -> ConfigOption:
    option = item.data
    if not isinstance(option, ConfigOption):
        raise ValueError(f"Invalid config item payload for {item.id}")
    return option
