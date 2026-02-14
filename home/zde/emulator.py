from __future__ import annotations

from common import HOME_DIR
from process import run, run_checked


def cmd_emulator(mode: str, query: str | None) -> int:
    status_rc = run(["/opt/penv/bin/supervisorctl", "status", mode])
    if status_rc == 3:
        if mode == "playground":
            run_checked(
                [
                    "/opt/penv/bin/python3",
                    str(HOME_DIR / "Zeal-Playground" / "tools" / "build_manifest.py"),
                    str(HOME_DIR / "Zeal-Playground" / "files"),
                    str(HOME_DIR / "Zeal-Playground" / "files" / "manifest.json"),
                ]
            )
        start_rc = run(["/opt/penv/bin/supervisorctl", "start", mode])
        if start_rc != 0:
            return start_rc
    elif status_rc != 0:
        return status_rc

    base = "http://127.0.0.1:1145/?r=latest&"
    if mode == "playground":
        base = "http://127.0.0.1:1155/?r=latest&"
    print(base + (query or ""))
    return 0


def cmd_emulator_stop(mode: str) -> int:
    status_rc = run(["/opt/penv/bin/supervisorctl", "status", mode])
    if status_rc == 0:
        return run(["/opt/penv/bin/supervisorctl", "stop", mode])
    return 0
