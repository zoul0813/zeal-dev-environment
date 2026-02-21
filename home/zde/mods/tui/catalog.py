from __future__ import annotations

from types import ModuleType

from mods.commands import (
    discover_command_modules,
    discover_subcommands,
    import_command_module,
    module_name_to_command,
)
from mods.tui.contract import ActionSpec, CommandSpec


def _module_action_overrides(module: ModuleType) -> dict[str, dict]:
    value = getattr(module, "TUI_ACTION_OVERRIDES", {})
    if not isinstance(value, dict):
        return {}
    result: dict[str, dict] = {}
    for key, raw in value.items():
        if not isinstance(key, str) or not isinstance(raw, dict):
            continue
        result[key] = raw
    return result


def _infer_command_spec(module_name: str, module: ModuleType) -> CommandSpec:
    command_name = module_name_to_command(module_name)
    subcommands = sorted(discover_subcommands(module).keys())
    overrides = _module_action_overrides(module)
    actions: list[ActionSpec] = []
    if subcommands:
        for sub in subcommands:
            override = overrides.get(sub, {})
            label = override.get("label", sub)
            help_text = override.get("help", "")
            default_args = override.get("default_args", [])
            if not isinstance(label, str):
                label = sub
            if not isinstance(help_text, str):
                help_text = ""
            if not isinstance(default_args, list) or any(not isinstance(item, str) for item in default_args):
                default_args = []
            pause_after_run = bool(override.get("pause_after_run", False))
            actions.append(
                ActionSpec(
                    id=sub,
                    label=label,
                    help=help_text,
                    default_args=list(default_args),
                    pause_after_run=pause_after_run,
                )
            )
    else:
        actions.append(ActionSpec(id="__main__", label="run"))
    return CommandSpec(name=command_name, label=command_name, actions=actions)


def _merge_action(base: ActionSpec, override: ActionSpec) -> ActionSpec:
    label = override.label if override.label else base.label
    help_text = override.help if override.help else base.help
    default_args = override.default_args if override.default_args else base.default_args
    pause_after_run = override.pause_after_run if override.pause_after_run != base.pause_after_run else base.pause_after_run
    return ActionSpec(
        id=base.id,
        label=label,
        help=help_text,
        default_args=list(default_args),
        pause_after_run=pause_after_run,
        excluded=bool(override.excluded),
    )


def _merge_specs(inferred: CommandSpec, explicit: CommandSpec) -> CommandSpec:
    merged_actions: list[ActionSpec] = []
    overrides_by_id = {action.id: action for action in explicit.actions}
    seen: set[str] = set()

    for action in inferred.actions:
        override = overrides_by_id.get(action.id)
        if override is None:
            merged_actions.append(action)
            seen.add(action.id)
            continue
        merged = _merge_action(action, override)
        seen.add(action.id)
        if merged.excluded:
            continue
        merged_actions.append(merged)

    for action in explicit.actions:
        if action.id in seen:
            continue
        if action.excluded:
            continue
        label = action.label if action.label else action.id
        merged_actions.append(
            ActionSpec(
                id=action.id,
                label=label,
                help=action.help,
                default_args=list(action.default_args),
                pause_after_run=action.pause_after_run,
                excluded=False,
            )
        )

    return CommandSpec(
        name=inferred.name,
        label=explicit.label if explicit.label else inferred.label,
        help=explicit.help if explicit.help else inferred.help,
        actions=merged_actions,
    )


def _command_spec_from_module(module_name: str, module: ModuleType) -> CommandSpec | None:
    inferred = _infer_command_spec(module_name, module)
    provider = getattr(module, "get_tui_spec", None)
    if callable(provider):
        spec = provider()
        if isinstance(spec, CommandSpec):
            return _merge_specs(inferred, spec)
    return inferred


def build_catalog() -> list[CommandSpec]:
    catalog: list[CommandSpec] = []
    for module_name in discover_command_modules():
        if module_name == "tui":
            continue
        module = import_command_module(module_name)
        spec = _command_spec_from_module(module_name, module)
        if spec is None:
            continue
        if not spec.actions:
            continue
        catalog.append(spec)
    return sorted(catalog, key=lambda item: item.label)
