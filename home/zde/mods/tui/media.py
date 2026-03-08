from __future__ import annotations

import base64
from dataclasses import dataclass
import fcntl
import io
import os
import shutil
import subprocess
import struct
import termios
import urllib.error
import urllib.request

from PIL import Image

from mods.config import Config


@dataclass(frozen=True)
class MediaEntry:
    kind: str
    index: int
    url: str

    @property
    def id(self) -> str:
        return f"{self.kind}:{self.index}"

    @property
    def label(self) -> str:
        return f"{self.kind} #{self.index + 1}: {self.url}"


def detect_native_image_protocol() -> str | None:
    override = os.environ.get("ZDE_TUI_IMAGE_PROTOCOL", "").strip().lower()
    if override in {"kitty", "iterm", "none"}:
        return None if override == "none" else override

    term_program = os.environ.get("TERM_PROGRAM", "").strip().lower()
    lc_terminal = os.environ.get("LC_TERMINAL", "").strip().lower()
    term = os.environ.get("TERM", "").strip().lower()
    if os.environ.get("KITTY_WINDOW_ID") or "kitty" in term:
        return "kitty"
    if term_program in {"wezterm", "ghostty"}:
        return "kitty"
    if term_program == "iterm.app" or "iterm" in term_program:
        return "iterm"
    if "iterm" in lc_terminal:
        return "iterm"
    if os.environ.get("ITERM_SESSION_ID"):
        return "iterm"
    if os.environ.get("ITERM_PROFILE"):
        return "iterm"
    for key in os.environ:
        if key.startswith("ITERM_"):
            return "iterm"
    return None


def native_media_supported() -> bool:
    return detect_native_image_protocol() is not None


def _screenshot_scale_factor() -> float:
    cfg = Config.load()
    raw = cfg.get("textual.screenshot-scale")
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        value = float(raw)
        if value > 0:
            return value
    return 1.0


def _fetch_bytes(url: str) -> bytes:
    with urllib.request.urlopen(url) as response:
        return response.read()


def _hyperlink(url: str, label: str) -> str:
    # OSC 8 hyperlinks are supported by many modern terminals.
    return f"\x1b]8;;{url}\x1b\\{label}\x1b]8;;\x1b\\"


def _normalize_to_4_3(image: Image.Image) -> Image.Image:
    target_ratio = 4.0 / 3.0
    src_ratio = image.width / max(1, image.height)
    if abs(src_ratio - target_ratio) < 0.0001:
        return image
    if src_ratio > target_ratio:
        target_width = int(image.height * target_ratio)
        left = max(0, (image.width - target_width) // 2)
        return image.crop((left, 0, left + target_width, image.height))
    target_height = int(image.width / target_ratio)
    top = max(0, (image.height - target_height) // 2)
    return image.crop((0, top, image.width, top + target_height))


def _render_geometry(max_cols: int, max_rows: int) -> tuple[int, int]:
    cols_limit = max(1, int(max_cols))
    rows_limit = max(1, int(max_rows))
    cols = min(cols_limit, max(1, (rows_limit * 4) // 3))
    rows = max(1, (cols * 3) // 4)
    if rows > rows_limit:
        rows = rows_limit
        cols = max(1, (rows * 4) // 3)
    return cols, rows


def _terminal_cell_ratio() -> float:
    # Return cell_height / cell_width. Fallback assumes cells are ~2x taller.
    try:
        packed = fcntl.ioctl(1, termios.TIOCGWINSZ, struct.pack("HHHH", 0, 0, 0, 0))
        rows, cols, xpix, ypix = struct.unpack("HHHH", packed)
        if rows > 0 and cols > 0 and xpix > 0 and ypix > 0:
            cell_w = xpix / cols
            cell_h = ypix / rows
            if cell_w > 0 and cell_h > 0:
                return cell_h / cell_w
    except Exception:
        pass
    return 2.0


def _render_geometry_for_kitty(max_cols: int, max_rows: int) -> tuple[int, int]:
    cols_limit = max(1, int(max_cols))
    rows_limit = max(1, int(max_rows))
    cell_ratio = max(1.0, _terminal_cell_ratio())
    target_cols_per_row = (4.0 / 3.0) * cell_ratio

    cols = min(cols_limit, max(1, int(rows_limit * target_cols_per_row)))
    rows = max(1, int(cols / target_cols_per_row))
    if rows > rows_limit:
        rows = rows_limit
        cols = max(1, int(rows * target_cols_per_row))
    return cols, rows


def _encode_png_4_3(payload: bytes) -> tuple[int, bytes | str]:
    try:
        image = Image.open(io.BytesIO(payload)).convert("RGB")
    except Exception as exc:
        return 1, f"Failed decoding screenshot image: {exc}"
    normalized = _normalize_to_4_3(image)
    out = io.BytesIO()
    normalized.save(out, format="PNG")
    return 0, out.getvalue()


def _emit_kitty_image(png_data: bytes, *, cols: int, rows: int) -> None:
    payload = base64.b64encode(png_data).decode("ascii")
    chunk_size = 4096
    first = True
    offset = 0
    while offset < len(payload):
        chunk = payload[offset : offset + chunk_size]
        offset += len(chunk)
        more = 1 if offset < len(payload) else 0
        if first:
            first = False
            params = f"a=T,f=100,t=d,c={cols},r={rows},m={more}"
        else:
            params = f"m={more}"
        print(f"\x1b_G{params};{chunk}\x1b\\", end="", flush=True)
    print("")


def _emit_iterm_image(png_data: bytes, *, cols: int, rows: int) -> None:
    payload = base64.b64encode(png_data).decode("ascii")
    # iTerm2 scales more predictably with percentage sizing than cell counts.
    # Reserve a few terminal lines for surrounding text/prompts so the image
    # doesn't push the viewport into scrollback.
    reserved_lines = 5
    safe_rows = max(8, rows)
    usable_rows = max(1, safe_rows - reserved_lines)
    height_pct = int((usable_rows / safe_rows) * 100)
    if height_pct < 50:
        height_pct = 50
    if height_pct > 95:
        height_pct = 95

    print(
        f"\x1b]1337;File=inline=1;width=100%;height={height_pct}%;preserveAspectRatio=1:{payload}\a",
        end="",
        flush=True,
    )
    print("")


def preview_image_url_native(url: str) -> int:
    protocol = detect_native_image_protocol()
    if protocol is None:
        print("Native terminal image protocol not detected.")
        print(f"URL: {_hyperlink(url, url)}")
        return 1
    # Clear screen and reset cursor to top-left before rendering image content.
    print("\x1b[2J\x1b[H", end="", flush=True)
    print("Loading screenshot...", end="", flush=True)
    try:
        payload = _fetch_bytes(url)
    except urllib.error.URLError as exc:
        print("\r\x1b[2K", end="", flush=True)
        print(f"Failed fetching screenshot URL: {exc}")
        print(f"URL: {url}")
        return 1
    rc, encoded = _encode_png_4_3(payload)
    print("\r\x1b[2K", end="", flush=True)
    if rc != 0:
        print(str(encoded))
        print(f"URL: {url}")
        return 1
    if not isinstance(encoded, bytes):
        print(str(encoded))
        print(f"URL: {url}")
        return 1

    terminal = shutil.get_terminal_size(fallback=(120, 40))
    # Use almost the full terminal viewport while leaving a tiny safety margin.
    avail_cols = max(20, terminal.columns - 1)
    avail_rows = max(8, terminal.lines - 2)
    scale = _screenshot_scale_factor()
    avail_cols = max(1, int(avail_cols * scale))
    avail_rows = max(1, int(avail_rows * scale))
    if protocol == "kitty":
        cols, rows = _render_geometry_for_kitty(avail_cols, avail_rows)
    else:
        cols, rows = _render_geometry(avail_cols, avail_rows)
    print(f"Screenshot preview: {_hyperlink(url, url)}")
    if protocol == "kitty":
        _emit_kitty_image(encoded, cols=cols, rows=rows)
        return 0
    if protocol == "iterm":
        _emit_iterm_image(encoded, cols=cols, rows=rows)
        return 0
    print("No supported renderer for detected protocol.")
    return 1


def play_video_url(url: str) -> int:
    for player in ("mpv", "ffplay"):
        executable = shutil.which(player)
        if executable is None:
            continue
        if player == "mpv":
            return subprocess.call([executable, url])
        return subprocess.call([executable, "-autoexit", url])

    print("No supported video player found in PATH (tried: mpv, ffplay).")
    print(f"Video URL: {_hyperlink(url, url)}")
    return 1
