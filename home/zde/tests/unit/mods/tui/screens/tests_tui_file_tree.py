from __future__ import annotations

from pathlib import Path

from mods.tui.panels.file_tree import FileTreeScreen
from mods.tui.panels.item_action_screen import ActionResult, ConfirmRequest, ItemEntry


class _FakeImage:
    def __init__(self) -> None:
        self.image_type = "cf"
        self._entries = [("dir1", "drwx dir1", True), ("file1", "-rw file1", False)]
        self.rm_calls: list[list[str]] = []

    def entries(self, relative_dir: Path):
        return list(self._entries)

    def rm(self, args: list[str]) -> int:
        self.rm_calls.append(args)
        return 0


def test_file_tree_logic(monkeypatch) -> None:
    fake_image = _FakeImage()
    monkeypatch.setattr("mods.tui.panels.file_tree.image_mod.get_image", lambda image_type: fake_image)
    screen = FileTreeScreen("cf")
    screen.get_items()

    actions = screen.get_actions()
    assert [a.id for a in actions] == ["open", "remove"]
    assert screen.is_action_visible("open", "dir1") is True
    assert screen.is_action_visible("open", "file1") is False
    assert screen.is_action_visible("remove", "..") is False
    assert screen.is_action_visible("anything", "file1") is True
    assert screen.preferred_action_id("dir1") == "open"
    assert screen.preferred_action_id("file1") == "refresh"

    rows = screen.get_items()
    assert [r.id for r in rows] == ["dir1", "file1"]
    screen._current_dir = Path("sub")
    rows2 = screen.get_items()
    assert rows2[0].id == ".."

    assert screen._relative_target("x") == "sub/x"
    screen._current_dir = Path(".")
    assert screen._navigate_to("..") is False
    screen._current_dir = Path("sub")
    assert screen._navigate_to("..") is True
    assert screen._current_dir == Path(".")
    assert screen._navigate_to("file1") is False
    screen._entry_is_dir["dir1"] = True
    assert screen._navigate_to("dir1") is True
    assert screen._current_dir == Path("dir1")


def test_file_tree_actions_and_confirm(monkeypatch) -> None:
    fake_image = _FakeImage()
    monkeypatch.setattr("mods.tui.panels.file_tree.image_mod.get_image", lambda image_type: fake_image)
    screen = FileTreeScreen("cf")

    # _run_capture captures output and int return.
    rc, output = screen._run_capture(lambda: print("hello") or 2)
    assert rc == 2
    assert "hello" in output

    assert screen.confirm_action("remove", "..") is None
    req = screen.confirm_action("remove", "file1")
    assert isinstance(req, ConfirmRequest)
    assert "Remove" in req.title
    assert screen.confirm_action("open", "file1") is None

    screen._entry_is_dir = {"dir1": True}
    open_ok = screen._action_open(ItemEntry(id="dir1", label="dir1"))
    assert isinstance(open_ok, ActionResult)
    assert open_ok.rc == 0
    open_bad = screen._action_open(ItemEntry(id="file1", label="file1"))
    assert open_bad.rc == 1

    remove_parent = screen._action_remove(ItemEntry(id="..", label=".."))
    assert remove_parent.rc == 1
    screen._current_dir = Path(".")
    remove_ok = screen._action_remove(ItemEntry(id="file1", label="file1"))
    assert remove_ok.rc == 0
