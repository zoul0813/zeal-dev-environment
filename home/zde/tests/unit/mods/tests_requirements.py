from __future__ import annotations

from dataclasses import dataclass

import pytest

from mods import requirements


@dataclass
class _Dep:
    installed: bool
    required: bool = False


class _Catalog:
    def __init__(self, deps: dict[str, _Dep], chains: dict[str, list[str]] | None = None, install_rc: int = 0) -> None:
        self._deps = deps
        self._chains = chains or {}
        self._install_rc = install_rc
        self.install_calls: list[tuple[str, bool, bool]] = []

    def get(self, dep_id: str):
        return self._deps.get(dep_id)

    def dependency_chain(self, dep_id: str) -> list[str]:
        return self._chains.get(dep_id, [dep_id])

    def install_dep(self, dep_id: str, *, allow_required: bool = False, include_dependencies: bool = True) -> int:
        self.install_calls.append((dep_id, allow_required, include_dependencies))
        return self._install_rc


def _catalog_factory(sequence: list[_Catalog]):
    idx = {"value": 0}

    def _factory():
        i = idx["value"]
        idx["value"] += 1
        return sequence[min(i, len(sequence) - 1)]

    return _factory


def test_find_missing_reports_unknown_and_uninstalled(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    cat = _Catalog({"dep-a": _Dep(installed=False)})
    monkeypatch.setattr(requirements, "DepCatalog", lambda: cat)
    missing = requirements._find_missing(["dep-a", "dep-missing"])
    out = capsys.readouterr().out
    assert missing == ["dep-a", "dep-missing"]
    assert "Warning: command requires unknown dep id: dep-missing" in out


def test_print_missing_renders_required_and_optional_sections(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    cat = _Catalog(
        {
            "req": _Dep(installed=False, required=True),
            "opt": _Dep(installed=False, required=False),
        }
    )
    monkeypatch.setattr(requirements, "DepCatalog", lambda: cat)
    requirements._print_missing(["req", "opt"])
    out = capsys.readouterr().out
    assert "Missing required dependencies for this command:" in out
    assert "zde update" in out
    assert 'zde deps install "opt"' in out


def test_install_missing_builds_unique_chain_and_skips_installed(monkeypatch: pytest.MonkeyPatch) -> None:
    cat = _Catalog(
        {
            "root": _Dep(installed=False),
            "dep-a": _Dep(installed=False),
            "dep-b": _Dep(installed=True),
        },
        chains={"root": ["dep-a", "dep-b", "root"], "dep-a": ["dep-a"]},
    )
    monkeypatch.setattr(requirements, "DepCatalog", lambda: cat)
    assert requirements._install_missing(["root", "dep-a"]) is True
    assert cat.install_calls == [
        ("dep-a", True, False),
        ("root", True, False),
    ]


def test_install_missing_returns_false_on_first_install_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    cat = _Catalog({"dep-a": _Dep(installed=False)}, chains={"dep-a": ["dep-a"]}, install_rc=5)
    monkeypatch.setattr(requirements, "DepCatalog", lambda: cat)
    assert requirements._install_missing(["dep-a"]) is False


def test_install_missing_skips_unknown_dep_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    cat = _Catalog({"known": _Dep(installed=False)}, chains={"known": ["known"]})
    monkeypatch.setattr(requirements, "DepCatalog", lambda: cat)
    assert requirements._install_missing(["unknown", "known"]) is True
    assert cat.install_calls == [("known", True, False)]


def test_require_deps_happy_path_no_requirements() -> None:
    assert requirements.require_deps([]) is True


def test_require_deps_returns_true_when_nothing_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requirements, "_find_missing", lambda ids: [])
    assert requirements.require_deps(["dep-a"]) is True


def test_require_deps_non_interactive_returns_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requirements, "_find_missing", lambda ids: ["dep-a"])
    monkeypatch.setattr(requirements, "_print_missing", lambda missing: None)
    monkeypatch.setattr(requirements.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(requirements.sys.stdout, "isatty", lambda: True)
    assert requirements.require_deps(["dep-a"]) is False


def test_require_deps_user_declines_install(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requirements, "_find_missing", lambda ids: ["dep-a"])
    monkeypatch.setattr(requirements, "_print_missing", lambda missing: None)
    monkeypatch.setattr(requirements.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(requirements.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "n")
    assert requirements.require_deps(["dep-a"]) is False


def test_require_deps_install_attempt_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(requirements, "_find_missing", lambda ids: ["dep-a"])
    monkeypatch.setattr(requirements, "_print_missing", lambda missing: None)
    monkeypatch.setattr(requirements.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(requirements.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    monkeypatch.setattr(requirements, "_install_missing", lambda missing: False)
    assert requirements.require_deps(["dep-a"]) is False


def test_require_deps_install_succeeds_and_recheck_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = {"count": 0}

    def _find_missing(ids):
        calls["count"] += 1
        return ["dep-a"] if calls["count"] == 1 else []

    monkeypatch.setattr(requirements, "_find_missing", _find_missing)
    monkeypatch.setattr(requirements, "_print_missing", lambda missing: None)
    monkeypatch.setattr(requirements.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(requirements.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "y")
    monkeypatch.setattr(requirements, "_install_missing", lambda missing: True)
    assert requirements.require_deps(["dep-a"]) is True


def test_require_deps_install_succeeds_but_missing_remains(monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(requirements, "_find_missing", lambda ids: ["dep-a"])
    monkeypatch.setattr(requirements, "_print_missing", lambda missing: None)
    monkeypatch.setattr(requirements.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(requirements.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": "yes")
    monkeypatch.setattr(requirements, "_install_missing", lambda missing: True)
    assert requirements.require_deps(["dep-a"]) is False
    out = capsys.readouterr().out
    assert "Dependencies are still missing after install/sync:" in out
