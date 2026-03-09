from __future__ import annotations

import sys
from pathlib import Path
from typing import NamedTuple

from mods.process import run


class ToolSpec(NamedTuple):
    path: Path
    required: bool = False


class ToolingSupport:
    _TOOLS: dict[str, ToolSpec] = {}

    def __init__(self) -> None:
        return None

    def _required_tools(self) -> list[str]:
        return [name for name, spec in self._TOOLS.items() if spec.required]

    def has_tool(self, names: list[str]) -> bool:
        for name in names:
            spec = self._TOOLS.get(name)
            if spec is None or not spec.path.is_file():
                return False
        return True

    def _missing_tools(self, names: list[str]) -> list[tuple[str, Path | None]]:
        missing: list[tuple[str, Path | None]] = []
        for name in names:
            spec = self._TOOLS.get(name)
            path = None if spec is None else spec.path
            if path is None or not path.is_file():
                missing.append((name, path))
        return missing

    def _require_tools(self, names: list[str]) -> bool:
        missing = self._missing_tools(names)
        if not missing:
            return True
        print("Missing tool(s):")
        for name, path in missing:
            if path is None:
                print(f"  - {name} (unknown tool key)")
            else:
                print(f"  - {name}: {path}")
        return False

    def _require_configured_tools(self) -> bool:
        return self._require_tools(self._required_tools())

    def _tool(self, name: str, args: list[str]) -> int:
        if not self._require_tools([name]):
            return 1
        tool_path = self._TOOLS[name].path
        return run([sys.executable, str(tool_path), *args])
