from __future__ import annotations

from types import SimpleNamespace

import pytest

from mods import cli


class _NoIsatty:
    pass


class _Stream:
    def __init__(self, is_tty: bool) -> None:
        self._is_tty = is_tty

    def isatty(self) -> bool:
        return self._is_tty


def test_infer_colors_enabled_respects_no_color_and_term(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    assert cli.infer_colors_enabled(stdout=_Stream(True)) is False
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "dUmB")
    assert cli.infer_colors_enabled(stdout=_Stream(True)) is False


def test_infer_colors_enabled_requires_callable_isatty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert cli.infer_colors_enabled(stdout=_NoIsatty()) is False
    assert cli.infer_colors_enabled(stdout=_Stream(False)) is False
    assert cli.infer_colors_enabled(stdout=_Stream(True)) is True


def test_colors_enabled_prefers_explicit_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli.Config,
        "load",
        lambda: SimpleNamespace(get_with_source=lambda key: (False, True)),
    )
    assert cli.colors_enabled(stdout=_Stream(True)) is False

    monkeypatch.setattr(
        cli.Config,
        "load",
        lambda: SimpleNamespace(get_with_source=lambda key: (True, True)),
    )
    assert cli.colors_enabled(stdout=_Stream(False)) is True


def test_colors_enabled_falls_back_to_infer_when_not_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli.Config,
        "load",
        lambda: SimpleNamespace(get_with_source=lambda key: (None, False)),
    )
    monkeypatch.setattr(cli, "infer_colors_enabled", lambda stdout=None: True)
    assert cli.colors_enabled(stdout=_Stream(False)) is True


def test_paint_unknown_color_and_disabled_color_paths(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "colors_enabled", lambda stdout=None: False)
    assert cli.paint("hello", "red") == "hello"
    assert cli.paint("hello", "magenta") == "hello"


def test_paint_wraps_text_when_color_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "colors_enabled", lambda stdout=None: True)
    rendered = cli.paint("hello", "green")
    assert rendered.startswith("\033[32m")
    assert rendered.endswith("\033[0m")
    assert "hello" in rendered
