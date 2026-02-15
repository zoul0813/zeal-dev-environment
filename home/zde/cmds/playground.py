from __future__ import annotations

from ._service import start as start_supervised_service
from ._service import stop as stop_supervised_service
from mods.common import HOME_DIR
from mods.process import run_checked


def subcmd_start(args: list[str]) -> int:
    query = args[0] if args else None

    run_checked(
        [
            "/opt/penv/bin/python3",
            str(HOME_DIR / "Zeal-Playground" / "tools" / "build_manifest.py"),
            str(HOME_DIR / "Zeal-Playground" / "files"),
            str(HOME_DIR / "Zeal-Playground" / "files" / "manifest.json"),
        ]
    )

    start_rc = start_supervised_service("playground")
    if start_rc != 0:
        return start_rc

    print("http://127.0.0.1:1155/?r=latest&" + (query or ""))
    return 0


def subcmd_stop(args: list[str]) -> int:
    return stop_supervised_service("playground")


def help() -> int:
    print("Usage: zde playground <subcommand> [query]")
    print("Subcommands:")
    print("  start [query]")
    print("  stop")
    return 0


def main(args: list[str]) -> int:
    return subcmd_start(args)
