from __future__ import annotations

from process import run


def main(args: list[str]) -> int:
    return run(["/bin/bash"])
