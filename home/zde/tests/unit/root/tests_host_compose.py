from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("runtime", ["docker", "podman"])
@pytest.mark.parametrize("provider", ["docker-compose", "podman-compose"])
@pytest.mark.parametrize("exit_code", [0, 7])
@pytest.mark.parametrize("no_tty", [False, True])
def test_container_launcher_preserves_io_arguments_and_status(tmp_path: Path, runtime: str, provider: str, exit_code: int, no_tty: bool) -> None:
    common = Path(__file__).resolve().parents[3] / "svcs" / "common.sh"
    executable = tmp_path / runtime
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, sys\n"
        "if sys.argv[-1] == '--help':\n"
        f"    print({'--interactive Keep STDIN open' if provider == 'docker-compose' else '--no-deps Do not start dependencies'!r})\n"
        "    sys.exit(0)\n"
        "print(json.dumps(sys.argv[1:]))\n"
        "sys.stdout.write(sys.stdin.read())\n"
        "sys.stderr.write('runtime stderr\\n')\n"
        f"sys.exit({exit_code})\n"
    )
    executable.chmod(0o755)
    env = dict(os.environ)
    env.update(
        CONTAINER_CMD=str(executable), COMPOSE_PATH="/compose path/compose.yml",
        HOST_UID="1000", HOST_GID="1000", HOST_HOME="/host home",
        HOST_CWD="/project dir", ZDE_SOFT_EXIT="1", TERM="xterm-256color",
        _ZDE_NO_TTY="1" if no_tty else "0",
    )
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; zde_run_in_container service sh -c "exit 7"', "bash", str(common)],
        input="stdin payload\n", text=True, capture_output=True, env=env,
    )
    arguments, payload = result.stdout.split("\n", 1)
    argv = json.loads(arguments)
    prefix = ["compose", "-f", env["COMPOSE_PATH"], "run"]
    if no_tty:
        prefix.append("-T")
        if provider == "docker-compose":
            prefix.append("--interactive=false")
        else:
            assert not any(arg.startswith("--interactive") for arg in argv)
        assert "-i" not in argv
    elif provider == "docker-compose":
        prefix.append("-i")
    else:
        assert "-i" not in argv
    prefix.append("--rm")
    assert argv[:len(prefix)] == prefix
    assert "--interactive" not in argv
    if not no_tty:
        assert "-T" not in argv
    for key in ["HOST_UID", "HOST_GID", "HOST_HOME", "HOST_CWD", "TERM"]:
        index = argv.index(f"{key}={env[key]}")
        assert argv[index - 1] == "-e"
    # Soft-exit policy belongs to the host wrapper; the launcher preserves status.
    assert not any(arg.startswith("ZDE_SOFT_EXIT=") for arg in argv)
    assert argv[-4:] == ["service", "sh", "-c", "exit 7"]
    assert payload == ("" if no_tty else "stdin payload\n")
    assert result.stderr == "runtime stderr\n"
    assert result.returncode == exit_code


@pytest.mark.parametrize("runtime", ["docker", "podman"])
@pytest.mark.parametrize("service", ["emulator", "playground"])
def test_browser_service_uses_native_platform(tmp_path: Path, runtime: str, service: str) -> None:
    common = Path(__file__).resolve().parents[3] / "svcs" / "common.sh"
    executable = tmp_path / runtime
    log = tmp_path / "commands.jsonl"
    executable.write_text(
        f"#!{sys.executable}\n"
        "import json, os, sys\n"
        "with open(os.environ['COMMAND_LOG'], 'a') as log:\n"
        "    log.write(json.dumps(sys.argv[1:]) + '\\n')\n"
    )
    executable.chmod(0o755)
    root = tmp_path / "zde"
    services = root / "home" / "zde" / "svcs"
    services.mkdir(parents=True)
    shutil.copy(common, services / "common.sh")
    shutil.copy(common.parent / service, services / service)
    (root / "bin").mkdir()
    browser = root / "bin" / "xdg-open"
    browser.write_text("#!/bin/sh\nexit 0\n")
    browser.chmod(0o755)
    state = tmp_path / "state"
    state.mkdir()
    dependency = "Zeal8bit/Zeal-WebEmulator" if service == "emulator" else "Zeal8bit/Zeal-Playground"
    (state / "deps-lock.yml").write_text(f"dependencies:\n  {dependency}:\n    repo: example\n")
    env = dict(os.environ, CONTAINER_CMD=str(executable), COMMAND_LOG=str(log),
               LAUNCH_PWD="/project", ZDE_PATH=str(root), ZDE_USER_PATH=str(state),
               ZDE_IMAGE_REF="example/zde:version")
    result = subprocess.run(
        ["bash", str(services / service), "start"],
        text=True, capture_output=True, env=env,
    )
    assert result.returncode == 0, result.stderr
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    runs = [args for args in commands if args[0] == "run"]
    assert len(runs) == (2 if service == "playground" else 1)
    for run in runs:
        assert "--platform" not in run
        assert env["ZDE_IMAGE_REF"] in run
    port = "1145" if service == "emulator" else "1155"
    directory = "/home/zeal8bit/Zeal-WebEmulator" if service == "emulator" else "/home/zeal8bit/Zeal-Playground"
    assert runs[-1][-6:] == ["python3", "-m", "http.server", "--directory", directory, port]
    if service == "playground":
        assert "/home/zeal8bit/Zeal-Playground/tools/build_manifest.py" in runs[0]
