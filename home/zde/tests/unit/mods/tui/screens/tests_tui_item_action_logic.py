from __future__ import annotations

from types import SimpleNamespace

from mods.tui.panels.item_action_screen import ActionResult, ItemAction, ItemActionScreen, ItemEntry


class _Screen(ItemActionScreen):
    REFRESH_ACTION = False

    def __init__(self) -> None:
        super().__init__(title="t", subtitle="s")

    def get_items(self):
        return []

    def get_actions(self):
        return []


def test_item_action_run_action_branches() -> None:
    screen = _Screen()
    screen._action_defs = {
        "ok": ItemAction(id="ok", label="ok", callback=lambda item: 0),
        "bad": ItemAction(id="bad", label="bad", callback=lambda item: (_ for _ in ()).throw(RuntimeError("x"))),
        "ret": ItemAction(id="ret", label="ret", callback=lambda item: ActionResult(rc=2, status="s")),
        "int": ItemAction(id="int", label="int", callback=lambda item: 3),
        "none": ItemAction(id="none", label="none", callback=lambda item: None),
        "nocb": ItemAction(id="nocb", label="nocb", callback=None),
    }
    screen._item_entries_by_id = {
        "a": ItemEntry(id="a", label="A"),
        "b": ItemEntry(id="b", label="B", action_ids=["ok"]),
    }

    result_refresh = screen.run_action("refresh", "a")
    assert result_refresh.refresh_items is True
    assert result_refresh.status == "[ok] refreshed"
    assert result_refresh.preferred_item_id is None

    assert screen.run_action("ok", None).rc == 1
    assert screen.run_action("ok", "missing").rc == 0
    assert screen.run_action("bad", "a").rc == 1
    assert screen.run_action("ret", "a").rc == 2
    assert screen.run_action("int", "a").rc == 3
    assert screen.run_action("none", "a").rc == 0
    assert screen.run_action("nocb", "a").rc == 0
    # item action filter branch
    assert screen.run_action("bad", "b").rc == 0


def test_item_action_visibility_shortcuts_and_helpers() -> None:
    screen = _Screen()
    screen._action_defs = {
        "a1": ItemAction(id="a1", label="A1", requires_item=True, shortcut="f3"),
        "a2": ItemAction(id="a2", label="A2", requires_item=False, shortcut="f5"),
        "a3": ItemAction(id="a3", label="A3", requires_item=True, shortcut=""),
    }
    screen._all_actions = list(screen._action_defs.values())
    screen._item_entries_by_id = {"x": ItemEntry(id="x", label="X", action_ids=["a1"])}

    assert screen.get_default_action_id() is None
    assert screen.preferred_action_id("x") is None
    assert screen.confirm_action("a1", "x") is None
    assert screen.is_action_visible("a2", None) is True
    assert screen.is_action_visible("a1", "x") is True
    assert screen.is_action_visible("a3", "x") is False
    assert screen.is_action_visible("a1", None) is True

    assert screen._is_group_heading_name("__group__:1") is True
    assert screen._is_group_heading_name("x") is False
    assert screen._is_selectable_item(None) is False
    assert screen._is_selectable_item(SimpleNamespace(name="__group__:x")) is False
    assert screen._is_selectable_item(SimpleNamespace(name="item")) is True

    screen._selected_item_id = lambda: "x"  # type: ignore[method-assign]
    assert screen._shortcut_action_for_key("  ") is None
    assert screen._shortcut_action_for_key("f3") == "a1"
    assert screen._shortcut_action_for_key("f5") == "a2"

    screen._selected_item_id = lambda: None  # type: ignore[method-assign]
    assert screen._shortcut_action_for_key("f3") is None
    assert screen._shortcut_action_for_key("f5") == "a2"
