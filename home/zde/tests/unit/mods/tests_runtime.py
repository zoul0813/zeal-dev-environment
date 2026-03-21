from __future__ import annotations

import pytest

from mods import runtime


def test_runtime_defaults_to_cli_mode() -> None:
    assert runtime.is_tui_mode() is False


def test_use_mode_switches_and_restores() -> None:
    original = runtime.is_tui_mode()
    with runtime.use_mode("tui"):
        assert runtime.is_tui_mode() is True
    assert runtime.is_tui_mode() is original


def test_use_mode_restores_after_exception() -> None:
    original = runtime.is_tui_mode()
    with pytest.raises(RuntimeError, match="boom"):
        with runtime.use_mode("tui"):
            assert runtime.is_tui_mode() is True
            raise RuntimeError("boom")
    assert runtime.is_tui_mode() is original
