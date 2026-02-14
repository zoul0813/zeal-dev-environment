from __future__ import annotations

from functools import partial

from common import HOME_DIR, dispatch_subcommand
from process import run, run_checked


def start_service(service: str, args: list[str]) -> int:
    query = args[0] if args else None
    status_rc = run(["/opt/penv/bin/supervisorctl", "status", service])
    if status_rc == 3:
        if service == "playground":
            run_checked(
                [
                    "/opt/penv/bin/python3",
                    str(HOME_DIR / "Zeal-Playground" / "tools" / "build_manifest.py"),
                    str(HOME_DIR / "Zeal-Playground" / "files"),
                    str(HOME_DIR / "Zeal-Playground" / "files" / "manifest.json"),
                ]
            )
        start_rc = run(["/opt/penv/bin/supervisorctl", "start", service])
        if start_rc != 0:
            return start_rc
    elif status_rc != 0:
        return status_rc

    base = "http://127.0.0.1:1145/?r=latest&"
    if service == "playground":
        base = "http://127.0.0.1:1155/?r=latest&"
    print(base + (query or ""))
    return 0


def stop_service(service: str, args: list[str]) -> int:
    status_rc = run(["/opt/penv/bin/supervisorctl", "status", service])
    if status_rc == 0:
        return run(["/opt/penv/bin/supervisorctl", "stop", service])
    if status_rc == 3:
        return 0
    return status_rc


def module_help(name: str) -> int:
    print(f"Usage: zde {name} <subcommand> [query]")
    print("Subcommands:")
    print("  start [query]")
    print("  stop")
    return 0


def main_for(name: str, service: str, args: list[str]) -> int:
    subcommands = {
        "start": partial(start_service, service),
        "stop": partial(stop_service, service),
    }
    return dispatch_subcommand(
        name,
        args,
        subcommands,
        default="start",
        help_fn=lambda: module_help(name),
    )


def main(args: list[str]) -> int:
    return main_for("emulator", "emulator", args)
