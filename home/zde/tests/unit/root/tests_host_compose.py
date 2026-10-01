from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.parametrize("runtime", ["docker", "podman"])
@pytest.mark.parametrize("provider", ["docker-compose", "podman-compose"])
@pytest.mark.parametrize("exit_code", [0, 7])
def test_container_launcher_preserves_io_arguments_and_status(tmp_path: Path, runtime: str, provider: str, exit_code: int) -> None:
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
    )
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; zde_run_in_container service sh -c "exit 7"', "bash", str(common)],
        input="stdin payload\n", text=True, capture_output=True, env=env,
    )
    arguments, payload = result.stdout.split("\n", 1)
    argv = json.loads(arguments)
    prefix = ["compose", "-f", env["COMPOSE_PATH"], "run"]
    if provider == "docker-compose":
        prefix.append("-i")
    else:
        assert "-i" not in argv
    prefix.append("--rm")
    assert argv[:len(prefix)] == prefix
    assert "--interactive" not in argv
    for key in ["HOST_UID", "HOST_GID", "HOST_HOME", "HOST_CWD", "TERM"]:
        index = argv.index(f"{key}={env[key]}")
        assert argv[index - 1] == "-e"
    # Soft-exit policy belongs to the host wrapper; the launcher preserves status.
    assert not any(arg.startswith("ZDE_SOFT_EXIT=") for arg in argv)
    assert argv[-4:] == ["service", "sh", "-c", "exit 7"]
    assert payload == "stdin payload\n"
    assert result.stderr == "runtime stderr\n"
    assert result.returncode == exit_code
