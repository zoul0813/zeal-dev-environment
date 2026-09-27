from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar

_auto_confirm: ContextVar[bool] = ContextVar("zde_auto_confirm", default=False)


@contextmanager
def confirmation_scope(yes: bool) -> Iterator[None]:
    token = _auto_confirm.set(yes)
    try:
        yield
    finally:
        _auto_confirm.reset(token)


def is_auto_confirm() -> bool:
    return _auto_confirm.get()


def confirm(prompt: str) -> bool:
    if is_auto_confirm():
        return True
    try:
        return input(prompt).strip().lower() in {"y", "yes"}
    except EOFError:
        return False
