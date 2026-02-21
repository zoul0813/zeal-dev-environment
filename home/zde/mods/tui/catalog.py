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


def _command_spec_from_module(module_name: str, module: ModuleType) -> CommandSpec | None:
    provider = getattr(module, "get_tui_spec", None)
    if callable(provider):
        spec = provider()
        if isinstance(spec, CommandSpec):
            return spec
    return _infer_command_spec(module_name, module)


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
