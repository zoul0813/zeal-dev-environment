from __future__ import annotations

import pytest

from cmds import sync


def test_sync_runs_maintenance_without_host_update(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(sync, "run_maintenance", lambda: calls.append("maintenance") or 0)

    assert sync.main([]) == 0
    assert calls == ["maintenance"]


def test_sync_rejects_arguments(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "run_maintenance", lambda: pytest.fail("maintenance should not run"))

    assert sync.main(["unexpected"]) == 1
