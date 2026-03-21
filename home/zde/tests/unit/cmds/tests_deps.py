from __future__ import annotations

from types import SimpleNamespace

import pytest

from cmds import deps as deps_cmd


class _FakeDep:
    def __init__(self, dep_id: str) -> None:
        self.id = dep_id


class _FakeCatalog:
    def __init__(self) -> None:
        self.install_calls: list[str] = []
        self.remove_calls: list[tuple[str, bool]] = []
        self._deps = {
            "core": _FakeDep("core"),
            "alias-core": _FakeDep("core"),
            "tools": _FakeDep("tools"),
        }

    def resolve(self, raw_id: str):
        return self._deps.get(raw_id)

    def install_dep(self, dep_id: str) -> int:
        self.install_calls.append(dep_id)
        return 0 if dep_id != "tools" else 5

    def get_dependents(self, dep_id: str) -> set[str]:
        return {"dependent"} if dep_id == "core" else set()

    def remove_dep(self, dep_id: str, force: bool = False) -> int:
        self.remove_calls.append((dep_id, force))
        return 0


def test_resolve_dep_ids_deduplicates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(deps_cmd, "DepCatalog", _FakeCatalog)
    catalog, dep_ids, rc = deps_cmd._resolve_dep_ids(["core", "alias-core"], "usage")
    assert rc == 0
    assert catalog is not None
    assert dep_ids == ["core"]


def test_subcmd_install_stops_on_first_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeCatalog()
    monkeypatch.setattr(deps_cmd, "DepCatalog", lambda: fake)
    rc = deps_cmd.subcmd_install(["core", "tools"])
    assert rc == 5
    assert fake.install_calls == ["core", "tools"]


def test_subcmd_remove_requires_confirmation(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fake = _FakeCatalog()
    monkeypatch.setattr(deps_cmd, "DepCatalog", lambda: fake)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    rc = deps_cmd.subcmd_remove(["tools"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "Aborted." in out
    assert fake.remove_calls == []


def test_subcmd_remove_blocks_when_dependents_exist(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    fake = _FakeCatalog()
    monkeypatch.setattr(deps_cmd, "DepCatalog", lambda: fake)
    rc = deps_cmd.subcmd_remove(["core"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "Cannot remove 'core': required by dependent" in out
    assert fake.remove_calls == []


def test_subcmd_stage_rejects_unknown_target(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(
        deps_cmd.image_mod,
        "images",
        lambda: [SimpleNamespace(image_type="cf"), SimpleNamespace(image_type="eeprom")],
    )
    monkeypatch.setattr(
        deps_cmd.image_mod,
        "get_image",
        lambda target: (_ for _ in ()).throw(ValueError("invalid target")),
    )
    rc = deps_cmd.subcmd_stage(["unknown", "core"])
    out = capsys.readouterr().out
    assert rc == 1
    assert "Target must be one of: cf, eeprom" in out
