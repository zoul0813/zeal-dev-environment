from __future__ import annotations

import io
import os
from types import SimpleNamespace

import pytest
from PIL import Image

from mods.tui import media


def _png_bytes(width: int, height: int) -> bytes:
    image_obj = Image.new("RGB", (width, height), color=(255, 0, 0))
    out = io.BytesIO()
    image_obj.save(out, format="PNG")
    return out.getvalue()


def test_protocol_detection_and_support(monkeypatch: pytest.MonkeyPatch) -> None:
    entry = media.MediaEntry(kind="screenshot", index=1, url="https://x")
    assert entry.id == "screenshot:1"
    assert entry.label == "screenshot #2: https://x"

    monkeypatch.setenv("ZDE_TUI_IMAGE_PROTOCOL", "kitty")
    assert media.detect_native_image_protocol() == "kitty"
    monkeypatch.setenv("ZDE_TUI_IMAGE_PROTOCOL", "none")
    assert media.detect_native_image_protocol() is None
    monkeypatch.delenv("ZDE_TUI_IMAGE_PROTOCOL", raising=False)

    monkeypatch.setenv("KITTY_WINDOW_ID", "1")
    assert media.detect_native_image_protocol() == "kitty"
    monkeypatch.delenv("KITTY_WINDOW_ID", raising=False)
    monkeypatch.setenv("TERM_PROGRAM", "iterm.app")
    assert media.detect_native_image_protocol() == "iterm"
    monkeypatch.setenv("TERM_PROGRAM", "wezterm")
    assert media.detect_native_image_protocol() == "kitty"
    monkeypatch.setenv("TERM_PROGRAM", "")
    monkeypatch.setenv("LC_TERMINAL", "iterm2")
    assert media.detect_native_image_protocol() == "iterm"
    monkeypatch.delenv("LC_TERMINAL", raising=False)
    monkeypatch.setenv("ITERM_SESSION_ID", "x")
    assert media.detect_native_image_protocol() == "iterm"
    monkeypatch.delenv("ITERM_SESSION_ID", raising=False)
    monkeypatch.setenv("ITERM_PROFILE", "x")
    assert media.detect_native_image_protocol() == "iterm"
    monkeypatch.delenv("ITERM_PROFILE", raising=False)
    monkeypatch.setenv("ITERM_X", "1")
    assert media.detect_native_image_protocol() == "iterm"
    monkeypatch.delenv("ITERM_X", raising=False)
    monkeypatch.setenv("TERM", "xterm")
    monkeypatch.setenv("TERM_PROGRAM", "")
    assert media.detect_native_image_protocol() is None

    monkeypatch.setattr(media, "detect_native_image_protocol", lambda: "kitty")
    assert media.native_media_supported() is True
    monkeypatch.setattr(media, "detect_native_image_protocol", lambda: None)
    assert media.native_media_supported() is False


def test_config_scale_hyperlink_geometry_and_normalize(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Cfg:
        def __init__(self, value) -> None:
            self.value = value

        def get(self, _key):
            return self.value

    monkeypatch.setattr(media.Config, "load", lambda: _Cfg(2))
    assert media._screenshot_scale_factor() == 2.0
    monkeypatch.setattr(media.Config, "load", lambda: _Cfg(0))
    assert media._screenshot_scale_factor() == 1.0
    monkeypatch.setattr(media.Config, "load", lambda: _Cfg(True))
    assert media._screenshot_scale_factor() == 1.0

    assert "example.com" in media._hyperlink("https://example.com", "https://example.com")

    same = Image.new("RGB", (400, 300))
    assert media._normalize_to_4_3(same).size == (400, 300)
    wider = Image.new("RGB", (500, 300))
    assert media._normalize_to_4_3(wider).size == (400, 300)
    taller = Image.new("RGB", (300, 500))
    assert media._normalize_to_4_3(taller).size == (300, 225)

    assert media._render_geometry(120, 40)[0] >= 1
    monkeypatch.setattr(media, "_terminal_cell_ratio", lambda: 2.0)
    assert media._render_geometry_for_kitty(120, 40)[0] >= 1


def test_terminal_cell_ratio_and_encode(monkeypatch: pytest.MonkeyPatch) -> None:
    packed = b"\x00" * 8
    monkeypatch.setattr(media.fcntl, "ioctl", lambda *_a, **_k: packed)
    monkeypatch.setattr(media.struct, "unpack", lambda _fmt, _p: (40, 120, 1200, 1600))
    ratio = media._terminal_cell_ratio()
    assert ratio > 0

    monkeypatch.setattr(media.fcntl, "ioctl", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("x")))
    assert media._terminal_cell_ratio() == 2.0

    rc, payload = media._encode_png_4_3(_png_bytes(400, 300))
    assert rc == 0
    assert isinstance(payload, bytes)
    rc, payload = media._encode_png_4_3(b"bad")
    assert rc == 1
    assert "Failed decoding screenshot image" in str(payload)
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"abc"

    monkeypatch.setattr(media.urllib.request, "urlopen", lambda _url: _Resp())
    assert media._fetch_bytes("https://x") == b"abc"


def test_emit_and_preview_image(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    media._emit_kitty_image(_png_bytes(10, 10), cols=10, rows=8)
    media._emit_iterm_image(_png_bytes(10, 10), cols=10, rows=8)

    monkeypatch.setattr(media, "detect_native_image_protocol", lambda: None)
    assert media.preview_image_url_native("https://x") == 1

    monkeypatch.setattr(media, "detect_native_image_protocol", lambda: "kitty")
    monkeypatch.setattr(media, "_fetch_bytes", lambda _url: (_ for _ in ()).throw(media.urllib.error.URLError("bad")))
    assert media.preview_image_url_native("https://x") == 1

    monkeypatch.setattr(media, "_fetch_bytes", lambda _url: b"data")
    monkeypatch.setattr(media, "_encode_png_4_3", lambda _p: (1, "decode error"))
    assert media.preview_image_url_native("https://x") == 1

    monkeypatch.setattr(media, "_encode_png_4_3", lambda _p: (0, "not-bytes"))
    assert media.preview_image_url_native("https://x") == 1

    monkeypatch.setattr(media, "_encode_png_4_3", lambda _p: (0, _png_bytes(10, 10)))
    monkeypatch.setattr(media.shutil, "get_terminal_size", lambda fallback=(120, 40): os.terminal_size((120, 40)))
    monkeypatch.setattr(media, "_screenshot_scale_factor", lambda: 1.0)
    called = {"kitty": 0, "iterm": 0}
    monkeypatch.setattr(media, "_emit_kitty_image", lambda *_a, **_k: called.__setitem__("kitty", called["kitty"] + 1))
    monkeypatch.setattr(media, "_emit_iterm_image", lambda *_a, **_k: called.__setitem__("iterm", called["iterm"] + 1))
    assert media.preview_image_url_native("https://x") == 0
    assert called["kitty"] == 1

    monkeypatch.setattr(media, "detect_native_image_protocol", lambda: "iterm")
    assert media.preview_image_url_native("https://x") == 0
    assert called["iterm"] == 1

    monkeypatch.setattr(media, "detect_native_image_protocol", lambda: "unknown")
    assert media.preview_image_url_native("https://x") == 1
    assert "No supported renderer for detected protocol." in capsys.readouterr().out

    # Geometry edge branches.
    assert media._render_geometry(1, 1) == (1, 1)
    monkeypatch.setattr(media, "_terminal_cell_ratio", lambda: 10.0)
    cols, rows = media._render_geometry_for_kitty(10, 1)
    assert rows == 1 and cols >= 1

    # iTerm clamp branches.
    media._emit_iterm_image(_png_bytes(10, 10), cols=10, rows=1)
    media._emit_iterm_image(_png_bytes(10, 10), cols=10, rows=500)


def test_play_video_url(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(media.shutil, "which", lambda name: "/usr/bin/mpv" if name == "mpv" else None)
    monkeypatch.setattr(media.subprocess, "call", lambda cmd: 7)
    assert media.play_video_url("https://v") == 7

    monkeypatch.setattr(media.shutil, "which", lambda name: "/usr/bin/ffplay" if name == "ffplay" else None)
    monkeypatch.setattr(media.subprocess, "call", lambda cmd: 8)
    assert media.play_video_url("https://v") == 8

    monkeypatch.setattr(media.shutil, "which", lambda name: None)
    assert media.play_video_url("https://v") == 1
    out = capsys.readouterr().out
    assert "No supported video player found" in out
