from __future__ import annotations

from mods.common import HOME_DIR
from mods.process import run


def main(args: list[str]) -> int:
    return run([str(HOME_DIR / "templates" / "create.sh"), *args])
