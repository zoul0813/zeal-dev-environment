from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
HOME_DIR = Path("/home/zeal8bit") if Path("/home/zeal8bit").is_dir() else SCRIPT_DIR.parent
MNT_DIR = Path("/mnt") if Path("/mnt").is_dir() else REPO_ROOT / "mnt"
ROMDISK_DIR = MNT_DIR / "romdisk"
USER_STATE_DIR = HOME_DIR / ".zeal8bit"

HELP_TEXT = "Help: update, status, start, stop, make, emu[lator], create, image, kernel, romdisk"

SubcommandHandler = Callable[[list[str]], int]


def infer_subcommand_help(module_name: str, subcommands: dict[str, SubcommandHandler]) -> int:
    visible = sorted(name for name in subcommands if not name.startswith("_"))
    print(f"Usage: zde {module_name} <subcommand> [args]")
    print("Subcommands:")
    for name in visible:
        print(f"  {name}")
    return 0


def dispatch_subcommand(
    module_name: str,
    args: list[str],
    subcommands: dict[str, SubcommandHandler],
    *,
    default: str | None = None,
    help_fn: Callable[[], int] | None = None,
) -> int:
    if args and args[0] == "help":
        if help_fn is not None:
            return help_fn()
        return infer_subcommand_help(module_name, subcommands)

    if args:
        subcmd = args[0]
        handler = subcommands.get(subcmd)
        if handler is not None:
            return handler(args[1:])

    if default is not None:
        handler = subcommands.get(default)
        if handler is None:
            print(f"Invalid default subcommand '{default}' for module '{module_name}'")
            return 1
        return handler(args)

    if help_fn is not None:
        help_fn()
    else:
        infer_subcommand_help(module_name, subcommands)
    return 1
