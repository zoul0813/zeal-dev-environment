from __future__ import annotations

import builtins
import importlib
import sys
from pathlib import Path

import pytest

from mods import config as config_mod
from mods.config import Config, ConfigOption


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("on", True),
        ("true", True),
        ("1", True),
        ("off", False),
        ("false", False),
        ("0", False),
        ("maybe", None),
    ],
)
def test_parse_bool_tokens(raw: str, expected: bool | None) -> None:
    assert Config.parse_bool(raw) is expected


def test_config_set_get_unset_roundtrip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "zde.conf.yml"
    monkeypatch.setattr(config_mod, "USER_STATE_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)

    cfg = Config.load()
    assert cfg.get_with_source("output.color") == (None, False)

    cfg.set("output.color", True)
    cfg.save()

    loaded = Config.load()
    assert loaded.get_with_source("output.color") == (True, True)

    removed = loaded.unset("output.color")
    assert removed is True
    assert loaded.get_with_source("output.color") == (None, False)


def test_config_legacy_path_fallback_and_cleanup() -> None:
    cfg = Config({"deps": {"skip_sync_installed": True}})
    assert cfg.get_with_source("deps.skip-sync-installed") == (True, True)

    cfg.set("deps.skip-sync-installed", False)
    assert cfg.data["deps"]["skip-sync-installed"] is False
    assert "skip_sync_installed" not in cfg.data["deps"]


def test_config_set_from_text_float_validation() -> None:
    cfg = Config()
    with pytest.raises(ValueError, match="greater than 0"):
        cfg.set_from_text("textual.screenshot-scale", "0")


def test_load_config_returns_empty_when_yaml_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "zde.conf.yml"
    config_file.write_text("output:\n  color: true\n", encoding="utf-8")
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)
    monkeypatch.setattr(config_mod, "yaml", None)
    assert config_mod.load_config() == {}


def test_load_config_returns_empty_when_yaml_document_not_mapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_file = tmp_path / "zde.conf.yml"
    config_file.write_text("- not-a-map\n", encoding="utf-8")
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)
    assert config_mod.load_config() == {}


def test_save_config_noop_when_yaml_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "zde.conf.yml"
    monkeypatch.setattr(config_mod, "USER_STATE_DIR", tmp_path)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_file)
    monkeypatch.setattr(config_mod, "yaml", None)
    config_mod.save_config({"x": 1})
    assert not config_file.exists()


def test_delete_path_false_when_branch_missing_or_leaf_missing() -> None:
    data = {"a": {"b": {"c": 1}}}
    assert config_mod._delete_path(data, ("x", "y")) is False
    assert config_mod._delete_path(data, ("a", "b", "missing")) is False


def test_options_iter_resolve_and_read_apis() -> None:
    opts = Config.options()
    assert "output.color" in opts
    iter_keys = [opt.key for opt in Config.iter_options()]
    assert iter_keys == sorted(iter_keys)
    assert Config.resolve_option(" output.color ").key == "output.color"
    assert Config.resolve_option("missing.key") is None

    cfg = Config({"output": {"color": True}})
    assert cfg.get("output.color") is True
    assert cfg.is_explicit("output.color") is True


def test_get_and_get_with_source_raise_keyerror_for_unknown() -> None:
    cfg = Config()
    with pytest.raises(KeyError):
        cfg.get_with_source("nope")
    with pytest.raises(KeyError):
        cfg.get("nope")
    with pytest.raises(KeyError):
        cfg.is_explicit("nope")


def test_coerce_fallback_to_default_for_wrong_types() -> None:
    cfg = Config(
        {
            "output": {"color": "yes"},
            "textual": {"screenshot-scale": True, "theme": 123},
        }
    )
    assert cfg.get_with_source("output.color") == (None, False)
    assert cfg.get_with_source("textual.screenshot-scale") == (1.0, False)
    assert cfg.get_with_source("textual.theme") == ("monokai", False)


def test_set_validation_errors_and_unknown_key() -> None:
    cfg = Config()
    with pytest.raises(KeyError):
        cfg.set("missing.key", "x")
    with pytest.raises(ValueError, match="Invalid boolean value"):
        cfg.set("output.color", "yes")
    with pytest.raises(ValueError, match="must be a number"):
        cfg.set("textual.screenshot-scale", "1.0")
    with pytest.raises(ValueError, match="greater than 0"):
        cfg.set("textual.screenshot-scale", 0)
    with pytest.raises(ValueError, match="must be a string"):
        cfg.set("textual.theme", 1)
    with pytest.raises(ValueError, match="cannot be empty"):
        cfg.set("textual.theme", "   ")


def test_set_from_text_bool_and_float_errors_and_unknown_key() -> None:
    cfg = Config()
    with pytest.raises(KeyError):
        cfg.set_from_text("missing.key", "x")
    with pytest.raises(ValueError, match="Expected: on/off"):
        cfg.set_from_text("output.color", "maybe")
    with pytest.raises(ValueError, match="Invalid numeric value"):
        cfg.set_from_text("textual.screenshot-scale", "not-a-number")
    with pytest.raises(ValueError, match="greater than 0"):
        cfg.set_from_text("textual.screenshot-scale", "-1")


def test_unset_unknown_key_raises() -> None:
    cfg = Config()
    with pytest.raises(KeyError):
        cfg.unset("missing.key")


def test_set_theme_cleans_legacy_tui_paths() -> None:
    cfg = Config(
        {
            "tui": {"textual": {"theme": "legacy", "other": "x"}},
            "textual": {"dark": True},
        }
    )
    cfg.set("textual.theme", "nord")
    assert cfg.data["textual"]["theme"] == "nord"
    assert "dark" not in cfg.data["textual"]
    assert "tui" not in cfg.data


def test_config_module_handles_yaml_import_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "yaml":
            raise ModuleNotFoundError("forced missing yaml")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    sys.modules.pop("mods.config", None)
    imported = importlib.import_module("mods.config")
    try:
        assert imported.yaml is None
    finally:
        monkeypatch.setattr(builtins, "__import__", original_import)
        sys.modules.pop("mods.config", None)
        importlib.import_module("mods.config")


def test_set_from_text_success_paths() -> None:
    cfg = Config()
    assert cfg.set_from_text("output.color", "on") is True
    assert cfg.set_from_text("textual.screenshot-scale", "1.5") == 1.5
    assert cfg.set_from_text("textual.theme", "nord") == "nord"


def test_coerce_value_internal_float_string_and_unknown_type_paths() -> None:
    cfg = Config()
    opt_float = Config.resolve_option("textual.screenshot-scale")
    opt_str = Config.resolve_option("textual.theme")
    assert opt_float is not None
    assert opt_str is not None
    assert cfg._coerce_value(opt_float, 2) == 2.0
    assert cfg._coerce_value(opt_str, "monokai") == "monokai"

    unknown = ConfigOption(
        key="x",
        path=("x",),
        value_type="str",  # type: ignore[arg-type]
        description="x",
        default_value=None,
    )
    unknown = ConfigOption(
        key=unknown.key,
        path=unknown.path,
        value_type="invalid",  # type: ignore[arg-type]
        description=unknown.description,
        default_value=unknown.default_value,
    )
    assert cfg._coerce_value(unknown, "anything") is None
