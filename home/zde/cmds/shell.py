from __future__ import annotations

from mods.process import run


def main(args: list[str]) -> int:
    return run(["/bin/bash"])
