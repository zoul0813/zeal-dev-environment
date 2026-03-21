from __future__ import annotations

import subprocess
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from mods.update import Env


@dataclass
class _Completed:
    returncode: int = 0
    stdout: str = ""
    stderr: str = ""


class FakeProcess:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self._responses: dict[tuple[str, ...], _Completed] = {}
        self._exceptions: dict[tuple[str, ...], Exception] = {}
        self.default = _Completed(returncode=0, stdout="", stderr="")

    def set_result(self, cmd: list[str], *, returncode: int = 0, stdout: str = "", stderr: str = "") -> None:
        self._responses[tuple(cmd)] = _Completed(returncode=returncode, stdout=stdout, stderr=stderr)

    def set_exception(self, cmd: list[str], exc: Exception) -> None:
        self._exceptions[tuple(cmd)] = exc

    def run(self, cmd: list[str], **kwargs: Any) -> _Completed:
        key = tuple(cmd)
        self.calls.append(list(cmd))
        exc = self._exceptions.get(key)
        if exc is not None:
            raise exc
        response = self._responses.get(key, self.default)
        if kwargs.get("check") and response.returncode != 0:
            raise subprocess.CalledProcessError(
                returncode=response.returncode,
                cmd=cmd,
                output=response.stdout,
                stderr=response.stderr,
            )
        return _Completed(returncode=response.returncode, stdout=response.stdout, stderr=response.stderr)

    def patch_subprocess(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(subprocess, "run", self.run)


class FakeGitOps:
    def __init__(self, monkeypatch: Any) -> None:
        self.monkeypatch = monkeypatch
        self.git_paths: set[str] = set()
        self.clone_rc = 0
        self.update_rc = 0
        self.current_commit_value = "deadbeef"
        self.clone_calls: list[tuple[str, str, str, str, bool]] = []
        self.update_calls: list[tuple[str, str, str, str, bool]] = []

    def _is_git_repo(self, path: Path) -> bool:
        return str(path) in self.git_paths

    def _clone_repo(self, path: Path, repo: str, ref_type: str, ref_value: str, *, fetch_tags: bool = False) -> int:
        self.clone_calls.append((str(path), repo, ref_type, ref_value, fetch_tags))
        if self.clone_rc == 0:
            self.git_paths.add(str(path))
        return self.clone_rc

    def _update_repo(self, path: Path, repo: str, ref_type: str, ref_value: str, *, fetch_tags: bool = False) -> int:
        self.update_calls.append((str(path), repo, ref_type, ref_value, fetch_tags))
        return self.update_rc

    def _current_commit(self, path: Path) -> str:
        return self.current_commit_value

    def patch_deps(self) -> None:
        self.monkeypatch.setattr("mods.deps.is_git_repo", self._is_git_repo)
        self.monkeypatch.setattr("mods.deps.clone_repo", self._clone_repo)
        self.monkeypatch.setattr("mods.deps.update_repo", self._update_repo)
        self.monkeypatch.setattr("mods.deps.current_commit", self._current_commit)

    def patch_update(self) -> None:
        self.monkeypatch.setattr("mods.update.is_git_repo", self._is_git_repo)
        self.monkeypatch.setattr("mods.update.clone_repo", self._clone_repo)
        self.monkeypatch.setattr("mods.update.update_repo", self._update_repo)
        self.monkeypatch.setattr("mods.update.current_commit", self._current_commit)


class FsBuilder:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, rel: str) -> Path:
        return self.root / rel

    def mkdir(self, rel: str) -> Path:
        path = self.path(rel)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_text(self, rel: str, text: str) -> Path:
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_yaml(self, rel: str, text: str) -> Path:
        return self.write_text(rel, text.strip() + "\n")

    def make_env(self, *, base: str = "") -> Env:
        prefix = (base.rstrip("/") + "/") if base else ""
        root = self.mkdir(f"{prefix}root")
        home = self.mkdir(f"{prefix}home")
        user = self.mkdir(f"{prefix}user")
        return Env(
            zde_root=root,
            zde_home=home,
            user_path=user,
            deps_file=self.path(f"{prefix}deps.yml"),
            lock_file=self.path(f"{prefix}user/deps-lock.yml"),
            collection_file=self.path(f"{prefix}user/collection.yml"),
            managed_env_file=self.path(f"{prefix}user/deps.env"),
        )


class _UrlopenResponse:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self) -> "_UrlopenResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return self.payload


class FakeUrlopen:
    def __init__(self) -> None:
        self.payload = b""
        self.error: Exception | None = None

    def set_payload(self, payload: bytes | str) -> None:
        self.payload = payload.encode("utf-8") if isinstance(payload, str) else payload
        self.error = None

    def set_url_error(self, message: str) -> None:
        self.error = urllib.error.URLError(message)

    def __call__(self, url: str, *args: Any, **kwargs: Any) -> _UrlopenResponse:
        if self.error is not None:
            raise self.error
        return _UrlopenResponse(self.payload)

    def patch(self, monkeypatch: Any) -> None:
        monkeypatch.setattr(urllib.request, "urlopen", self)


class FakeTty:
    def __init__(self, *, tty: bool = True) -> None:
        self._tty = tty
        self.writes: list[str] = []
        self.flushed = False

    def isatty(self) -> bool:
        return self._tty

    def write(self, value: str) -> int:
        self.writes.append(value)
        return len(value)

    def flush(self) -> None:
        self.flushed = True
