from __future__ import annotations

import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
ZDE_PYTHON_ROOT = REPO_ROOT / "home" / "zde"
TESTS_ROOT = Path(__file__).resolve().parent
if str(ZDE_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(ZDE_PYTHON_ROOT))
if str(TESTS_ROOT) not in sys.path:
    sys.path.insert(0, str(TESTS_ROOT))


@pytest.fixture(autouse=True)
def _isolated_user_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ZDE_USER_PATH", str(tmp_path / "user-state"))


@pytest.fixture
def fs_builder(tmp_path: Path):
    from helpers.mocks import FsBuilder

    return FsBuilder(tmp_path)


@pytest.fixture
def env_factory(fs_builder):
    return fs_builder.make_env


@pytest.fixture
def fake_process(monkeypatch: pytest.MonkeyPatch):
    from helpers.mocks import FakeProcess

    fake = FakeProcess()
    fake.patch_subprocess(monkeypatch)
    return fake


@pytest.fixture
def fake_urlopen(monkeypatch: pytest.MonkeyPatch):
    from helpers.mocks import FakeUrlopen

    fake = FakeUrlopen()
    fake.patch(monkeypatch)
    return fake


@pytest.fixture
def fake_git(monkeypatch: pytest.MonkeyPatch):
    from helpers.mocks import FakeGitOps

    return FakeGitOps(monkeypatch)
