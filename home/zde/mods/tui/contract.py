from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ActionSpec:
    id: str
    label: str = ""
    help: str = ""
    default_args: list[str] = field(default_factory=list)
    pause_after_run: bool = False
    excluded: bool = False


@dataclass
class CommandSpec:
    name: str
    label: str
    help: str = ""
    actions: list[ActionSpec] = field(default_factory=list)
