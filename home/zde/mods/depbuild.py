from __future__ import annotations

import os
from pathlib import Path


def run_dep_build(dep: dict, dep_path: Path) -> int:
    build = dep.get("build")
    if not isinstance(build, dict):
        return 0

    tool = build.get("tool")
    args = build.get("args", [])
    if not isinstance(args, list):
        print(f"Invalid build.args for dependency: {dep.get('id', dep.get('path', '<unknown>'))}")
        return 1

    if tool not in {"cmake", "make"}:
        print(f"Invalid build.tool for dependency: {dep.get('id', dep.get('path', '<unknown>'))}")
        return 1

    for arg in args:
        if not isinstance(arg, str):
            print(f"Invalid non-string build arg for dependency: {dep.get('id', dep.get('path', '<unknown>'))}")
            return 1

    print(f"Building dependency: {dep['id']} ({tool})")
    old_cwd = Path.cwd()
    try:
        os.chdir(dep_path)
        if tool == "cmake":
            from cmds import cmake as cmd_cmake

            return int(cmd_cmake.main(args))

        from cmds import make as cmd_make

        return int(cmd_make.main(args))
    finally:
        os.chdir(old_cwd)
