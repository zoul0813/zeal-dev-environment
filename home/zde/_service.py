from __future__ import annotations

from process import run


SUPERVISORCTL = ["sudo", "/opt/penv/bin/supervisorctl"]


def run_supervisorctl(args: list[str]) -> int:
    return run([*SUPERVISORCTL, *args])


def start(service: str) -> int:
    status_rc = run_supervisorctl(["status", service])
    if status_rc == 3:
        return run_supervisorctl(["start", service])
    if status_rc == 0:
        return 0
    return status_rc


def stop(service: str) -> int:
    status_rc = run_supervisorctl(["status", service])
    if status_rc == 0:
        return run_supervisorctl(["stop", service])
    if status_rc == 3:
        return 0
    return status_rc
