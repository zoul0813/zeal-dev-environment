from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator, Literal

RuntimeMode = Literal["cli", "tui"]


@dataclass
class _RuntimeState:
    mode: RuntimeMode = "cli"


_STATE = _RuntimeState()


def is_tui_mode() -> bool:
    return _STATE.mode == "tui"


@contextmanager
def use_mode(mode: RuntimeMode) -> Iterator[None]:
    previous = _STATE.mode
    _STATE.mode = mode
    try:
        yield
    finally:
        _STATE.mode = previous
