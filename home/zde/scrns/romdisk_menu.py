from __future__ import annotations

from mods.tui.screens.file_tree import FileTreeScreen


class RomdiskMenuScreen(FileTreeScreen):
    def __init__(self) -> None:
        super().__init__("romdisk")
