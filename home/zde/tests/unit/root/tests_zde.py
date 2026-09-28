from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import zde as zde_router
from mods.confirmation import is_auto_confirm


REPO_ROOT = Path(__file__).resolve().parents[5]
WRAPPER = REPO_ROOT / "zde"
ROUTER = REPO_ROOT / "home" / "zde" / "zde.py"


def _stub_runtime(tmp_path: Path) -> Path:
    runtime = tmp_path / "container-runtime"
    runtime.write_text(
        '#!/bin/sh\n'
        'if [ -n "${STUB_LOG:-}" ]; then\n'
        '  printf "%s" "${ZDE_IMAGE_REF:-}" > "$STUB_LOG"\n'
        'fi\n'
        'exit "${STUB_RC:-0}"\n',
        encoding="utf-8",
    )
    runtime.chmod(0o755)
    return runtime


def _run_wrapper(
    tmp_path: Path,
    args: list[str],
    *,
    tty: bool,
    soft_exit: str | None = None,
    strict_exit: str | None = None,
    extra_env: dict[str, str] | None = None,
    stub_rc: int = 7,
) -> int:
    env = dict(os.environ)
    env.update(
        {
            "CONTAINER_CMD": str(_stub_runtime(tmp_path)),
            "STUB_RC": str(stub_rc),
            "ZDE_USER_PATH": str(tmp_path / "state"),
        }
    )
    for name, value in (("ZDE_SOFT_EXIT", soft_exit), ("ZDE_STRICT_EXIT", strict_exit)):
        if value is None:
            env.pop(name, None)
        else:
            env[name] = value
    if extra_env:
        env.update(extra_env)

    command = [str(WRAPPER), *args]
    if not tty:
        return subprocess.run(
            command,
            cwd=tmp_path,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=10,
        ).returncode

    master_fd, slave_fd = os.openpty()
    try:
        return subprocess.run(
            command,
            cwd=tmp_path,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=slave_fd,
            stderr=slave_fd,
            check=False,
            timeout=10,
        ).returncode
    finally:
        os.close(slave_fd)
        os.close(master_fd)


def test_main_prints_top_help_when_no_args(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(zde_router, "discover_command_modules", lambda: ["config", "deps"])
    rc = zde_router.main([])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Commands:" in out
    assert "config, deps" in out


def test_main_handles_host_service_alias(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    rc = zde_router.main(["emu"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "'emulator' is a host-only service command." in out
    assert "Run it from the host wrapper: ./zde emulator" in out


def test_main_unknown_module_falls_back_to_top_help(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(zde_router, "discover_command_modules", lambda: ["deps"])

    def _raise(module_name: str):
        raise ModuleNotFoundError("missing", name=f"cmds.{module_name}")

    monkeypatch.setattr(zde_router, "import_command_module", _raise)
    rc = zde_router.main(["unknown"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Unknown command module: unknown" in out
    assert "Commands:" in out


def test_main_routes_legacy_romdisk_redirect(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, list[str]] = {}

    def _main(args: list[str]) -> int:
        calls["args"] = args
        return 0

    monkeypatch.setattr(zde_router, "import_command_module", lambda module_name: SimpleNamespace(main=_main))
    monkeypatch.setattr(zde_router, "discover_subcommands", lambda module: {})
    rc = zde_router.main(["romdisk", "ls"])
    assert rc == 0
    assert calls["args"] == ["romdisk", "ls"]


def test_main_dispatches_subcommand_handler(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(zde_router, "import_command_module", lambda module_name: SimpleNamespace(main=lambda args: 99))
    monkeypatch.setattr(zde_router, "discover_subcommands", lambda module: {"list": lambda args: 7})
    rc = zde_router.main(["deps", "list", "games"])
    assert rc == 7


def test_main_honors_required_deps_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    module = SimpleNamespace(main=lambda args: 0, REQUIRED_DEPS=["dep-a"])
    monkeypatch.setattr(zde_router, "import_command_module", lambda module_name: module)
    monkeypatch.setattr(zde_router, "discover_subcommands", lambda module: {})
    monkeypatch.setattr(zde_router, "require_deps", lambda dep_ids: False)
    rc = zde_router.main(["kernel"])
    assert rc == 1


@pytest.mark.parametrize("args", [["config", "get", "bad-key"], ["exec", "false"]])
@pytest.mark.parametrize("tty", [False, True])
def test_wrapper_preserves_failures_by_default(tmp_path: Path, args: list[str], tty: bool) -> None:
    assert _run_wrapper(tmp_path, args, tty=tty) == 7


@pytest.mark.parametrize("args", [["config", "get", "bad-key"], ["exec", "false"]])
@pytest.mark.parametrize("tty", [False, True])
def test_wrapper_soft_exit_is_explicit_and_consistent(tmp_path: Path, args: list[str], tty: bool) -> None:
    assert _run_wrapper(tmp_path, args, tty=tty, soft_exit="1") == 0


@pytest.mark.parametrize("args", [["config", "get", "bad-key"], ["exec", "false"]])
@pytest.mark.parametrize("tty", [False, True])
def test_wrapper_strict_exit_overrides_soft_exit(tmp_path: Path, args: list[str], tty: bool) -> None:
    assert _run_wrapper(tmp_path, args, tty=tty, soft_exit="1", strict_exit="1") == 7


def test_router_does_not_rewrite_failure_status(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["ZDE_SOFT_EXIT"] = "1"
    env["ZDE_USER_PATH"] = str(tmp_path / "state")

    completed = subprocess.run(
        [sys.executable, str(ROUTER), "config", "get", "bad-key"],
        cwd=tmp_path,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        timeout=10,
    )

    assert completed.returncode != 0


@pytest.mark.parametrize(
    ("image_env", "expected"),
    [
        ({"ZDE_IMAGE_REF": "example/zde:review"}, "example/zde:review"),
        ({"ZDE_IMAGE_REF": "localhost:5000/example/zde:review"}, "localhost:5000/example/zde:review"),
        ({"ZDE_IMAGE_REF": f"example/zde@sha256:{'a' * 64}"}, f"example/zde@sha256:{'a' * 64}"),
        (
            {"ZDE_IMAGE": "localhost:5000/example/zde", "ZDE_VERSION": "dev"},
            "localhost:5000/example/zde:dev",
        ),
    ],
)
def test_wrapper_uses_one_resolved_image_reference(
    tmp_path: Path, image_env: dict[str, str], expected: str
) -> None:
    log = tmp_path / "image-ref.log"
    clean_image_env = {
        "ZDE_IMAGE_REF": "",
        "ZDE_IMAGE": "zoul0813/zeal-dev-environment",
        "ZDE_VERSION": "latest",
    }
    clean_image_env.update(image_env)
    clean_image_env["STUB_LOG"] = str(log)

    assert (
        _run_wrapper(tmp_path, ["config", "list"], tty=False, extra_env=clean_image_env, stub_rc=0) == 0
    )
    assert log.read_text(encoding="utf-8") == expected


@pytest.mark.parametrize(
    ("reference", "repository_tag"),
    [
        ("localhost:5000/example/zde:review", "localhost:5000/example/zde:cached"),
        (f"example/zde@sha256:{'a' * 64}", "example/zde:cached"),
    ],
)
def test_version_fallback_handles_registry_ports_and_digests(
    tmp_path: Path, reference: str, repository_tag: str
) -> None:
    runtime = tmp_path / "image-runtime"
    runtime.write_text(
        '#!/bin/sh\n'
        'if [ "$1" = "images" ]; then\n'
        '  printf "%s\\n" "$STUB_IMAGE_TAG"\n'
        'fi\n',
        encoding="utf-8",
    )
    runtime.chmod(0o755)
    env = dict(os.environ)
    env.update(
        {
            "CONTAINER_CMD": str(runtime),
            "STUB_IMAGE_TAG": repository_tag,
            "ZDE_IMAGE_REF": reference,
            "ZDE_USER_PATH": str(tmp_path / "state"),
        }
    )

    completed = subprocess.run(
        [str(WRAPPER), "--version"],
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
        text=True,
        timeout=10,
    )

    assert completed.returncode == 0
    assert f"Image: {reference}" in completed.stdout
    assert f"  - {repository_tag}" in completed.stdout


@pytest.mark.parametrize("argv", [
    ["-y", "deps", "remove", "tools"],
    ["deps", "remove", "tools", "--yes"],
])
def test_main_scopes_yes_flag(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> None:
    seen: list[tuple[list[str], bool]] = []
    monkeypatch.setattr(zde_router, "import_command_module", lambda name: SimpleNamespace(main=lambda args: 0))
    monkeypatch.setattr(zde_router, "discover_subcommands", lambda module: {
        "remove": lambda args: seen.append((args, is_auto_confirm())) or 0,
    })

    assert zde_router.main(argv) == 0
    assert seen == [(["tools"], True)]
    assert is_auto_confirm() is False
