from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path


def publish_rom_image(source: Path, roms_dir: Path, filename: str) -> tuple[Path, Path]:
    if Path(filename).name != filename:
        raise ValueError(f"ROM filename must not contain a path: {filename}")

    roms_dir.mkdir(parents=True, exist_ok=True)
    destination = roms_dir / filename
    latest = roms_dir / "latest.img"

    with tempfile.TemporaryDirectory(prefix=".rom-publish.", dir=roms_dir) as temporary_dir:
        temporary_root = Path(temporary_dir)
        staged_image = temporary_root / filename
        staged_latest = temporary_root / latest.name
        shutil.copy2(source, staged_image)
        staged_latest.symlink_to(Path(filename))
        os.replace(staged_image, destination)
        os.replace(staged_latest, latest)

    return destination, latest
