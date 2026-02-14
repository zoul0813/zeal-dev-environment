from __future__ import annotations

import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None) -> int:
    try:
        return subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=False).returncode
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}")
        return 127


def run_checked(cmd: list[str], cwd: Path | None = None) -> None:
    subprocess.run(cmd, cwd=str(cwd) if cwd else None, check=True)
