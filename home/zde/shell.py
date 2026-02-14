from __future__ import annotations

from process import run


def interactive_shell() -> int:
    return run(["/bin/bash"])
