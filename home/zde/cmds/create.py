from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

from mods.common import HOME_DIR
from mods.tui.contract import ActionSpec, CommandSpec


def _templates_dir() -> Path:
    module_home_dir = Path(__file__).resolve().parents[2]
    candidates = [
        HOME_DIR / "templates",
        module_home_dir / "templates",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


def _template_names() -> list[str]:
    names: list[str] = []
    templates_dir = _templates_dir()
    if not templates_dir.is_dir():
        return names
    for child in sorted(templates_dir.iterdir(), key=lambda p: p.name):
        if child.is_dir():
            names.append(child.name)
    return names


def list_templates() -> list[str]:
    return _template_names()


def _print_usage() -> int:
    print("# ZDE Create Project")
    print("Usage: zde create <template-name> [--name <project-name>] [args...]\n")
    print("Available Templates:\n")
    for name in _template_names():
        print(f"    > {name}")
    print("")
    return 0


def _print_templates() -> int:
    for name in _template_names():
        print(f"template: {name}")
    return 0


def _resolve_template_arg(template: str) -> str:
    local_template = _templates_dir() / template
    if local_template.is_dir():
        return str(local_template)
    return template


def _parse_create_args(args: list[str]) -> tuple[str, str | None, list[str], bool]:
    template = args[0]
    name: str | None = None
    extras: list[str] = []
    i = 1
    while i < len(args):
        arg = args[i]
        if arg == "--name":
            if i + 1 >= len(args):
                print("Missing value for --name")
                return template, None, [], False
            name = args[i + 1].strip()
            i += 2
            continue
        if arg.startswith("--name="):
            name = arg.split("=", 1)[1].strip()
            i += 1
            continue
        # Backward compatibility with old syntax.
        if arg.startswith("name="):
            name = arg.split("=", 1)[1].strip()
            i += 1
            continue
        extras.append(arg)
        i += 1
    return template, name, extras, True


def _prompt_name() -> str | None:
    while True:
        try:
            value = input("Project name: ").strip()
        except EOFError:
            return None
        if value:
            return value
        print("Project name cannot be empty.")


def _cookiecutter_bin() -> str | None:
    cookiecutter = shutil.which("cookiecutter")
    if cookiecutter:
        return cookiecutter
    penv_cookiecutter = Path("/opt/penv/bin/cookiecutter")
    if penv_cookiecutter.is_file():
        return str(penv_cookiecutter)
    return None


def main(args: list[str]) -> int:
    if not args:
        return _print_usage()
    if len(args) == 1 and args[0] == "-t":
        return _print_templates()

    cookiecutter = _cookiecutter_bin()
    if cookiecutter is None:
        print("Command not found: cookiecutter")
        return 127

    template_arg, project_name, extras, ok = _parse_create_args(args)
    if not ok:
        return 2
    if project_name is None:
        project_name = _prompt_name()
    if not project_name:
        print("A project name is required. Use --name <project-name>.")
        return 1

    env = dict(os.environ)
    env["ZDE_CREATE_OUT"] = "/src"
    out_dir = Path(env.get("ZDE_CREATE_OUT", "/tmp"))
    project_dir = out_dir / project_name
    if project_dir.exists():
        print(f"Project path already exists: {project_dir}")
        return 1

    template = _resolve_template_arg(template_arg)
    cmd = [
        cookiecutter,
        "--no-input",
        "-f",
        "-o",
        str(out_dir),
        template,
        f"name={project_name}",
        *extras,
    ]
    try:
        return subprocess.run(cmd, check=False, env=env).returncode
    except FileNotFoundError as exc:
        print(f"Command not found: {exc.filename}")
        return 127


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="create",
        label="create",
        help="Create a new project from templates",
        actions=[
            ActionSpec(
                id="open",
                label="open",
                help="Open template selection screen",
            )
        ],
    )


def get_tui_screen():
    from mods.tui.screens.create_menu import CreateMenuScreen

    return CreateMenuScreen()
