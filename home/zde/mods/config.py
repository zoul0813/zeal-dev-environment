from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from mods.common import USER_STATE_DIR

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


CONFIG_FILE = USER_STATE_DIR / "zde.conf.yml"
ConfigType = Literal["bool", "str"]


@dataclass(frozen=True)
class ConfigOption:
    key: str
    path: tuple[str, ...]
    value_type: ConfigType
    description: str
    default_value: Any
    legacy_paths: tuple[tuple[str, ...], ...] = ()


_OPTIONS: dict[str, ConfigOption] = {
    "output.color": ConfigOption(
        key="output.color",
        path=("output", "color"),
        value_type="bool",
        description="Enable or disable ANSI color output; unset uses terminal auto-detect",
        default_value=None,
    ),
    "textual.theme": ConfigOption(
        key="textual.theme",
        path=("textual", "theme"),
        value_type="str",
        description="Textual UI theme name",
        default_value="solarized-dark",
        legacy_paths=(("tui", "textual", "theme"),),
    ),
    "deps.skip-sync-installed": ConfigOption(
        key="deps.skip-sync-installed",
        path=("deps", "skip-sync-installed"),
        value_type="bool",
        description="Skip git sync for already-installed dependencies during update",
        default_value=False,
        legacy_paths=(("deps", "skip_sync_installed"),),
    ),
}


def load_config() -> dict[str, Any]:
    if not CONFIG_FILE.is_file():
        return {}
    if yaml is None:
        return {}
    with CONFIG_FILE.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        return {}
    return data


def save_config(data: dict[str, Any]) -> None:
    USER_STATE_DIR.mkdir(parents=True, exist_ok=True)
    if yaml is None:
        return
    with CONFIG_FILE.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=True)


def _read_path(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current


def _write_path(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = data
    for key in path[:-1]:
        child = current.get(key)
        if not isinstance(child, dict):
            child = {}
            current[key] = child
        current = child
    current[path[-1]] = value


def _delete_path(data: dict[str, Any], path: tuple[str, ...]) -> bool:
    stack: list[tuple[dict[str, Any], str]] = []
    current: Any = data
    for key in path[:-1]:
        if not isinstance(current, dict) or key not in current:
            return False
        stack.append((current, key))
        current = current[key]
    if not isinstance(current, dict) or path[-1] not in current:
        return False
    del current[path[-1]]

    for parent, key in reversed(stack):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            del parent[key]
        else:
            break
    return True


def _parse_bool(raw: str) -> bool | None:
    token = raw.strip().lower()
    if token in {"on", "true", "1", "yes", "y"}:
        return True
    if token in {"off", "false", "0", "no", "n"}:
        return False
    return None


class Config:
    def __init__(self, data: dict[str, Any] | None = None) -> None:
        self._data = data if isinstance(data, dict) else {}

    @classmethod
    def load(cls) -> "Config":
        return cls(load_config())

    @property
    def data(self) -> dict[str, Any]:
        return self._data

    @staticmethod
    def options() -> dict[str, ConfigOption]:
        return _OPTIONS

    @staticmethod
    def iter_options() -> list[ConfigOption]:
        return [option for _, option in sorted(_OPTIONS.items(), key=lambda item: item[0])]

    @staticmethod
    def resolve_option(name: str) -> ConfigOption | None:
        normalized = name.strip()
        return _OPTIONS.get(normalized)

    @staticmethod
    def parse_bool(raw: str) -> bool | None:
        return _parse_bool(raw)

    def _read_option_raw(self, option: ConfigOption) -> Any:
        value = _read_path(self._data, option.path)
        if value is not None:
            return value
        for legacy_path in option.legacy_paths:
            value = _read_path(self._data, legacy_path)
            if value is not None:
                return value
        return None

    def _coerce_value(self, option: ConfigOption, value: Any) -> Any:
        if option.value_type == "bool":
            if isinstance(value, bool):
                return value
            return None
        if option.value_type == "str":
            if isinstance(value, str):
                return value
            return None
        return None

    def get_with_source(self, key: str) -> tuple[Any, bool]:
        option = self.resolve_option(key)
        if option is None:
            raise KeyError(key)
        raw = self._read_option_raw(option)
        value = self._coerce_value(option, raw)
        if value is None:
            return option.default_value, False
        return value, True

    def get(self, key: str) -> Any:
        value, _ = self.get_with_source(key)
        return value

    def is_explicit(self, key: str) -> bool:
        _, explicit = self.get_with_source(key)
        return explicit

    def _cleanup_option(self, option: ConfigOption) -> None:
        for legacy_path in option.legacy_paths:
            _delete_path(self._data, legacy_path)
        if option.path == ("textual", "theme"):
            _delete_path(self._data, ("textual", "dark"))
            _delete_path(self._data, ("tui", "textual"))
            _delete_path(self._data, ("tui",))

    def set(self, key: str, value: Any) -> Any:
        option = self.resolve_option(key)
        if option is None:
            raise KeyError(key)
        if option.value_type == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"Invalid boolean value for {option.key}: {value}")
            normalized: Any = bool(value)
        else:
            if not isinstance(value, str):
                raise ValueError(f"Value for {option.key} must be a string")
            normalized = value.strip()
            if not normalized:
                raise ValueError(f"Value for {option.key} cannot be empty")
        _write_path(self._data, option.path, normalized)
        self._cleanup_option(option)
        return normalized

    def set_from_text(self, key: str, raw_value: str) -> Any:
        option = self.resolve_option(key)
        if option is None:
            raise KeyError(key)
        if option.value_type == "bool":
            parsed = _parse_bool(raw_value)
            if parsed is None:
                raise ValueError(
                    f"Invalid boolean value for {option.key}: {raw_value}\n"
                    "Expected: on/off, true/false, yes/no, 1/0"
                )
            return self.set(option.key, parsed)
        return self.set(option.key, raw_value)

    def unset(self, key: str) -> bool:
        option = self.resolve_option(key)
        if option is None:
            raise KeyError(key)
        removed = _delete_path(self._data, option.path)
        self._cleanup_option(option)
        return removed

    def save(self) -> None:
        save_config(self._data)
