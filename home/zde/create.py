from __future__ import annotations

from common import HOME_DIR
from process import run


def main(args: list[str]) -> int:
    return run([str(HOME_DIR / "templates" / "create.sh"), *args])
