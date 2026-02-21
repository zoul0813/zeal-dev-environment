from __future__ import annotations

from pathlib import Path
from typing import Any

from mods.common import USER_STATE_DIR

try:
    import yaml
except ModuleNotFoundError:
    yaml = None


CONFIG_FILE = USER_STATE_DIR / "zde.conf.yml"


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

