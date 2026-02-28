from __future__ import annotations

import os
import sys

from mods.config import Config


def infer_colors_enabled(stdout: object | None = None) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    term = os.environ.get("TERM", "")
    if term.lower() == "dumb":
        return False
    stream = sys.stdout if stdout is None else stdout
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    return bool(isatty())


def colors_enabled(stdout: object | None = None) -> bool:
    config = Config.load()
    value, explicit = config.get_with_source("output.color")
    if explicit:
        return bool(value)
    return infer_colors_enabled(stdout=stdout)


def paint(text: str, color: str, stdout: object | None = None) -> str:
    codes = {
        "white": "\033[37m",
        "red": "\033[31m",
        "yellow": "\033[33m",
        "green": "\033[32m",
    }
    code = codes.get(color)
    if code is None:
        return text
    if not colors_enabled(stdout=stdout):
        return text
    return f"{code}{text}\033[0m"
