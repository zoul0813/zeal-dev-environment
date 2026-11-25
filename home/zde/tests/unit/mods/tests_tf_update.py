from __future__ import annotations

import asyncio
import hashlib
import io
import shutil
import subprocess
import urllib.error
import zipfile
from contextlib import nullcontext
from pathlib import Path

import pytest

import zde
from mods import community_image, image
from mods.tooling import ToolSpec


@pytest.fixture
def tf(tmp_path, monkeypatch):
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt")
    monkeypatch.setattr(image, "require_deps", lambda _deps: True)
    monkeypatch.setattr(image.ImageTf, "_require_configured_tools", lambda _self: True)
    return image.get_image("tf")


def _bundle(payload, *, checksum=None):
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("tf-16mib.img", payload)
        checksum = hashlib.sha256(payload).hexdigest() if checksum is None else checksum
        bundle.writestr("tf-16mib.img.sha256", f"{checksum}  tf-16mib.img\n")
        bundle.writestr("licenses/notice.txt", "notice")
    return archive.getvalue()


@pytest.mark.parametrize("failure", ["missing release", "bad zip", "wrong size", "bad checksum", "too large"])
def test_invalid_download_never_runs_merge(tf, monkeypatch, capsys, failure):
    tf.path.parent.mkdir()
    tf.path.write_bytes(b"original")
    monkeypatch.setattr(tf, "_merge_supported", lambda: True)
    monkeypatch.setattr(image, "run", lambda _cmd: pytest.fail("ran merge with invalid download"))

    def open_url(url, *, timeout):
        assert url.endswith("/releases/latest/download/tf-16mib.img.zip")
        assert timeout > 0
        if failure == "missing release":
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, None)
        if failure == "bad checksum":
            return io.BytesIO(_bundle(bytes(16 * 1024**2), checksum="0" * 64))
        if failure == "wrong size":
            return io.BytesIO(_bundle(b"too small"))
        if failure == "too large":
            monkeypatch.setattr(community_image, "_MAX_DOWNLOAD_SIZE", 2)
        return io.BytesIO(b"invalid archive")

    monkeypatch.setattr(community_image.urllib.request, "urlopen", open_url)
    assert zde.main(["image", "tf", "update", "--yes"]) == 1
    assert tf.path.read_bytes() == b"original"
    assert "Failed to update TF image" in capsys.readouterr().out


def test_tf_update_validates_prerequisites_and_excludes_concurrent_create(tf, monkeypatch, capsys):
    assert tf.update([]) == 1
    assert "zde image tf create" in capsys.readouterr().out
    tf.path.write_bytes(b"original")
    monkeypatch.setattr(tf, "_merge_supported", lambda: False)
    assert tf.update([]) == 1
    assert "'zde deps update disk-tool' followed by 'zde deps build disk-tool'" in capsys.readouterr().out

    with image._tf_image_lock(tf.path.parent):
        assert tf.update(["--dry-run"]) == 1
        assert tf.create([]) == 1
    assert capsys.readouterr().out.count("Another ZDE command") == 2
    assert tf.path.read_bytes() == b"original"


def test_tf_update_cli_and_image_browser(tf, monkeypatch, capsys):
    from textual.app import App
    from textual.widgets import Label, ListView, Static

    from scrns import image_menu

    calls = []
    monkeypatch.setattr(tf, "update", lambda args: calls.append(args) or 0)
    assert zde.main(["image", "tf", "update", "--dry-run"]) == 0
    assert zde.main(["image", "eeprom", "update"]) == 0
    assert "Unknown subcommand" in capsys.readouterr().out
    assert calls == [["--dry-run"]]

    screen = image_menu.ImageMenuScreen()
    monkeypatch.setattr(image_menu, "suspend_for_external_output", lambda _app: nullcontext())
    monkeypatch.setattr(screen, "_pause_after_run", lambda: None)

    class BrowserApp(App):
        CSS_PATH = Path(image.__file__).with_name("tui") / "style.tcss"

    async def run_browser():
        app = BrowserApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await app.push_screen(screen)
            media_list = screen.query_one("#item-list", ListView)
            items = [row.name for row in media_list.children]
            for item in items:
                media_list.index = items.index(item)
                await pilot.pause()
                actions = screen.query_one("#item-actions", ListView)
                assert any(row.name == "update" for row in actions.children) == (item == "tf")
            media_list.index = items.index("tf")
            await pilot.pause()
            actions = screen.query_one("#item-actions", ListView)
            row = next(row for row in actions.children if row.name == "update")
            assert row.region.width >= row.query_one(Label).region.width == len("Update from Software Collection")
            await pilot.press("f6")
            assert "TF image is up to date" in str(screen.query_one("#item-status", Static).content)

    asyncio.run(run_browser())
    assert calls == [["--dry-run"], []]


@pytest.mark.parametrize("scenario", ["success", "conflict", "full"])
def test_tf_update_real_merge(tf, tmp_path, monkeypatch, capfd, scenario):
    zdt = shutil.which("zdt") or tf._TOOLS["zdt"].path
    if not shutil.which(zdt):
        pytest.skip("zdt is unavailable")
    monkeypatch.setattr(tf, "_TOOLS", {"zdt": ToolSpec(zdt, required=True)})
    if not tf._merge_supported():
        pytest.skip("zdt merge is unavailable")

    def disk(*args):
        subprocess.run([str(zdt), "--yes", *map(str, args)], check=True)

    source = tmp_path / "source.img"
    disk("image", "create", source, "--size", "16MiB", "--mbr")
    disk("-i", source, "partition", "create", "--alignment", "512B")
    content = tmp_path / "content"
    content.write_bytes(bytes(128 * 1024) if scenario == "full" else b"community file")
    disk("-i", source, "import", content, "/app")
    disk("-i", source, "import", content, "/new")
    archive = _bundle(source.read_bytes())
    monkeypatch.setattr(community_image.urllib.request, "urlopen", lambda *_a, **_kw: io.BytesIO(archive))

    tf.root.mkdir(parents=True)
    (tf.root / "personal").write_bytes(b"my file")
    if scenario == "conflict":
        (tf.root / "app").mkdir()
    else:
        (tf.root / "app").write_bytes(b"old app")
    assert tf.create(["64"]) == 0
    original = tf.path.read_bytes()

    command = ["image", "tf", "update"]
    if scenario != "success":
        assert zde.main([*command, "--yes"]) == 1
        assert tf.path.read_bytes() == original
        diagnostic = capfd.readouterr().err.lower()
        assert ("conflict" if scenario == "conflict" else "space") in diagnostic
        return

    assert zde.main([*command, "--dry-run", "--yes"]) == 0
    assert tf.path.read_bytes() == original

    # Without a terminal or --yes, zdt declines the merge.
    run = image.run

    def run_without_tty(cmd, **kwargs):
        if "merge" in cmd:
            return subprocess.call(cmd, stdin=subprocess.DEVNULL)
        return run(cmd, **kwargs)

    monkeypatch.setattr(image, "run", run_without_tty)
    assert zde.main(command) == 3
    assert tf.path.read_bytes() == original
    assert zde.main([*command, "--yes"]) == 0
    updated = tf.path.read_bytes()
    assert len(updated) == len(original)
    assert updated[:512] == original[:512]
    exported = tmp_path / "exported"
    disk("-i", tf.path, "export", "/", exported)
    assert (exported / "app").read_bytes() == (exported / "new").read_bytes() == b"community file"
    assert (exported / "personal").read_bytes() == b"my file"
    assert (tf.root / "app").read_bytes() == b"old app"
    assert zde.main(command) == 0
    assert tf.path.read_bytes() == updated
    assert "Merge: unchanged" in capfd.readouterr().out
