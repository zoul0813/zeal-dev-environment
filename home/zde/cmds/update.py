from __future__ import annotations

from pathlib import Path

from mods.process import run


def _run_or_fail(cmd: list[str]) -> int:
    rc = run(cmd)
    if rc != 0:
        return rc
    return 0


def main(args: list[str]) -> int:
    print("Running in-container update tasks")

    # Refresh nested submodules in mounted repos if present.
    for repo in [
        Path("/home/zeal8bit/Zeal-WebEmulator"),
        Path("/home/zeal8bit/Zeal-Playground"),
        Path("/home/zeal8bit/Zeal-8-bit-OS"),
    ]:
        if not repo.is_dir():
            continue
        rc = _run_or_fail(["git", "-C", str(repo), "submodule", "update", "--init", "--recursive"])
        if rc != 0:
            return rc

    # Regenerate playground manifest when sources are available.
    manifest_tool = Path("/home/zeal8bit/Zeal-Playground/tools/build_manifest.py")
    files_dir = Path("/home/zeal8bit/Zeal-Playground/files")
    manifest_out = files_dir / "manifest.json"
    if manifest_tool.is_file() and files_dir.is_dir():
        rc = _run_or_fail(["/opt/penv/bin/python3", str(manifest_tool), str(files_dir), str(manifest_out)])
        if rc != 0:
            return rc

    print("In-container update tasks complete")
    return 0
