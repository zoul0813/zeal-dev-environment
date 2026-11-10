from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[5]
BUILDER = "docker.io/zoul0813/zde-builder"
ZDE = "docker.io/zoul0813/zeal-dev-environment"


@pytest.fixture
def release(tmp_path: Path):
    shutil.copy(REPO_ROOT / "build.sh", tmp_path / "build.sh")
    (tmp_path / "build").mkdir()
    (tmp_path / "build" / "sdcc-src-4.4.0.tar.bz2").touch()
    fetch = tmp_path / "build" / "zeal8bit.sh"
    fetch.write_text("#!/bin/sh\nexit 0\n")
    fetch.chmod(0o755)
    executable = tmp_path / "podman"
    executable.write_text(
        f"#!{sys.executable}\n" + '''import json, os, sys
from pathlib import Path
args = sys.argv[1:]
with Path('commands.jsonl').open('a') as log:
    log.write(json.dumps(args) + '\\n')
if os.environ.get('FAIL_COMMAND') and ' '.join(args).startswith(os.environ['FAIL_COMMAND']):
    sys.exit(42)
if args[:2] == ['image', 'inspect']:
    arch = args[2].rsplit('-', 1)[-1]
    if arch == os.environ.get('MISSING_ARCH'):
        sys.exit(1)
    print('linux/' + (os.environ.get('WRONG_ARCH') or arch))
if args[:2] == ['image', 'exists']:
    sys.exit(0 if os.environ.get('LEGACY_IMAGE') or os.environ.get('MANIFEST_EXISTS') else 1)
if args[:2] == ['manifest', 'exists']:
    sys.exit(0 if os.environ.get('MANIFEST_EXISTS') else 1)
if args[:1] == ['search']:
    print('latest\\n1.2.2\\n1.2.3')
'''
    )
    executable.chmod(0o755)

    def run(*, rebuild=False, local=False, publish=True, version="1.2.4", **overrides):
        env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}",
                   USE_LOCAL_ZDE_BUILDER="true" if local else "false")
        env.update(overrides)
        # Each read consumes a single character. Newlines would answer the next prompt.
        answers = ("y" if rebuild else "n") + "y" + ("y" if rebuild else "") + ("y" if publish else "n")
        result = subprocess.run(["bash", str(tmp_path / "build.sh"), *([version] if version else [])],
                                cwd=tmp_path, env=env, input=answers, text=True, capture_output=True)
        commands = [json.loads(line) for line in (tmp_path / "commands.jsonl").read_text().splitlines()]
        return result, commands

    return run


@pytest.mark.parametrize("rebuild,local", [(False, False), (False, True), (True, False), (True, True)])
def test_release_builds_matching_architectures_and_publishes_manifests(release, rebuild, local):
    result, commands = release(rebuild=rebuild, local=local)
    assert result.returncode == 0, result.stderr
    builds = [c for c in commands if c[0] == "build"]
    runtime_builds = [c for c in builds if "-f" not in c]
    assert len(runtime_builds) == 2
    for arch, build in zip(("amd64", "arm64"), runtime_builds):
        assert build[build.index("--platform") + 1] == f"linux/{arch}"
        assert f"ZDE_BUILDER_IMAGE={BUILDER}:latest-{arch}" in build
        assert f"{ZDE}:1.2.4-{arch}" in build
    pulls = [c for c in commands if c[0] == "pull"]
    assert len(pulls) == (0 if local or rebuild else 2)
    if rebuild:
        assert len(builds) == 4
        assert max(commands.index(c) for c in builds[:2]) < commands.index(runtime_builds[0])
    for repo in ([BUILDER, ZDE] if rebuild else [ZDE]):
        manifest = next(c for c in commands if c[:2] == ["manifest", "create"] and c[2].startswith(repo + ":"))
        assert manifest[3:] == [manifest[2] + "-amd64", manifest[2] + "-arm64"]
        pushes = [c for c in commands if c[:2] == ["manifest", "push"] and c[3] == manifest[2]]
        assert pushes == [["manifest", "push", "--all", manifest[2], f"docker://{manifest[2]}"],
                          ["manifest", "push", "--all", manifest[2], f"docker://{repo}:latest"]]
    first_push = next(i for i, c in enumerate(commands) if c[:2] == ["manifest", "push"])
    assert all(commands.index(c) < first_push for c in builds)


@pytest.mark.parametrize("overrides", [{"MISSING_ARCH": "arm64"}, {"WRONG_ARCH": "amd64"}])
def test_invalid_local_builder_stops_before_runtime_builds(release, overrides):
    result, commands = release(local=True, **overrides)
    assert result.returncode != 0
    assert not any(c[0] == "build" or c[:2] == ["manifest", "push"] for c in commands)
    assert "builder" in result.stderr.lower()


@pytest.mark.parametrize("failure", ["pull", "build --platform linux/arm64", "manifest create"])
def test_build_failure_never_publishes(release, failure):
    result, commands = release(FAIL_COMMAND=failure)
    assert result.returncode != 0
    assert not any(c[:2] == ["manifest", "push"] for c in commands)


def test_declining_publish_keeps_local_images(release):
    result, commands = release(publish=False)
    assert "built locally" in result.stdout
    assert any(c[:2] == ["manifest", "create"] for c in commands)
    assert not any(c[:2] == ["manifest", "push"] for c in commands)


def test_version_is_optional_and_existing_manifest_tag_is_replaced(release):
    result, commands = release(version=None, MANIFEST_EXISTS="1")
    assert result.returncode == 0, result.stderr
    assert ["manifest", "rm", f"{ZDE}:1.2.4"] in commands
    assert not any(c[0] == "untag" for c in commands)


def test_push_failure_stops_before_latest(release):
    result, commands = release(FAIL_COMMAND="manifest push")
    assert result.returncode != 0
    assert len([c for c in commands if c[:2] == ["manifest", "push"]]) == 1


def test_legacy_single_image_tag_can_be_replaced_by_manifest(release):
    result, commands = release(LEGACY_IMAGE="1")
    assert result.returncode == 0, result.stderr
    untag = ["untag", f"{ZDE}:1.2.4", f"{ZDE}:1.2.4"]
    assert untag in commands
    assert commands.index(untag) < next(i for i, c in enumerate(commands)
                                        if c[:3] == ["manifest", "create", f"{ZDE}:1.2.4"])


def test_version_lookup_failure_stops_before_builds(release):
    result, commands = release(version=None, FAIL_COMMAND="search")
    assert result.returncode != 0
    assert not any(c[0] == "build" for c in commands)
