from __future__ import annotations

from pathlib import Path

import pytest

from mods import tooling


class _Support(tooling.ToolingSupport):
    _TOOLS = {
        "ok": tooling.ToolSpec(Path("/tmp/ok.py"), required=True),
        "opt": tooling.ToolSpec(Path("/tmp/opt.py"), required=False),
    }


def test_required_tools_and_has_tool(monkeypatch: pytest.MonkeyPatch) -> None:
    support = _Support()
    monkeypatch.setattr(Path, "is_file", lambda self: str(self) == "/tmp/ok.py")
    assert support._required_tools() == ["ok"]
    assert support.has_tool(["ok"]) is True
    assert support.has_tool(["opt"]) is False
    assert support.has_tool(["missing"]) is False


def test_missing_tools_reports_unknown_and_missing_path(monkeypatch: pytest.MonkeyPatch) -> None:
    support = _Support()
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    missing = support._missing_tools(["ok", "missing"])
    assert ("ok", Path("/tmp/ok.py")) in missing
    assert ("missing", None) in missing


def test_require_tools_prints_and_returns_false_for_missing(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    support = _Support()
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    assert support._require_tools(["ok", "missing"]) is False
    out = capsys.readouterr().out
    assert "Missing tool(s):" in out
    assert "ok: /tmp/ok.py" in out
    assert "missing (unknown tool key)" in out


def test_require_tools_and_require_configured_tools_success(monkeypatch: pytest.MonkeyPatch) -> None:
    support = _Support()
    monkeypatch.setattr(Path, "is_file", lambda self: str(self) == "/tmp/ok.py")
    assert support._require_tools(["ok"]) is True
    assert support._require_configured_tools() is True


def test_tool_invocation(monkeypatch: pytest.MonkeyPatch) -> None:
    support = _Support()

    # Missing tool branch.
    monkeypatch.setattr(Path, "is_file", lambda self: False)
    assert support._tool("ok", ["--x"]) == 1

    # Happy path branch.
    monkeypatch.setattr(Path, "is_file", lambda self: True)
    calls: list[list[str]] = []
    monkeypatch.setattr(tooling, "run", lambda cmd: calls.append(cmd) or 7)
    rc = support._tool("ok", ["--x"])
    assert rc == 7
    assert calls and calls[0][1:] == ["/tmp/ok.py", "--x"]
