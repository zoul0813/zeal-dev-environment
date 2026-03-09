from __future__ import annotations

from typing import Any

from mods.kernel import list_dep_kernel_configs, list_kernel_configs, list_kernel_options, run_kernel, run_kernel_tui_action
from mods.tui.contract import ActionSpec, CommandSpec


def subcmd_user(args: list[str]) -> int:
    return run_kernel(["user", *args])


def subcmd_menuconfig(args: list[str]) -> int:
    return run_kernel(["menuconfig", *args])


def help() -> int:
    print("Usage: zde kernel <config|dep-id|dep-alias|user|menuconfig|default>")
    config_names = list_kernel_configs()
    if config_names:
        print("Available configs:")
        print("  " + ", ".join(config_names))
    dep_configs = list_dep_kernel_configs()
    if dep_configs:
        print("Dependency configs:")
        for dep_cfg in dep_configs:
            aliases = ", ".join(dep_cfg.aliases) if dep_cfg.aliases else "-"
            print(f"  {dep_cfg.dep_id} (aliases: {aliases})")
    print("Examples:")
    if config_names:
        print(f"  zde kernel {config_names[0]}")
    else:
        print("  zde kernel zeal8bit")
    print("  zde kernel user")
    print("  zde kernel menuconfig")
    print("  zde kernel default")
    return 0


def main(args: list[str]) -> int:
    if not args:
        return help()
    return run_kernel(args)


def run_tui_action(action_id: str, context: dict[str, Any]) -> int:
    return run_kernel_tui_action(action_id, context)


def get_tui_spec() -> CommandSpec:
    actions = [
        ActionSpec(
            id=option.action_id,
            label=option.label,
            help=option.help,
            default_args=option.args,
        )
        for option in list_kernel_options()
    ]
    actions.append(ActionSpec(id="menuconfig", label="menuconfig", help="Open kernel menuconfig and persist user config"))
    actions.append(ActionSpec(id="default", label="default", help="Create default kernel config"))
    return CommandSpec(
        name="kernel",
        label="kernel",
        help="Build kernel with target/user configs",
        actions=actions,
    )
