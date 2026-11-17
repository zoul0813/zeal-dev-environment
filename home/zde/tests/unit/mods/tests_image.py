from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess

import pytest

from mods import image
from mods.confirmation import confirmation_scope
from mods.tooling import ToolSpec


def test_image_path_helpers_copy_entries_and_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    mnt = tmp_path / "mnt"
    monkeypatch.setattr(image, "MNT_DIR", mnt)

    img = image.Image("x", supports_directories=False)
    assert img._normalize_stage_root(None) == Path(".")
    assert img._normalize_stage_root(" ") == Path(".")
    assert img._normalize_stage_root("/") == Path(".")
    assert img._normalize_stage_root("/apps/bin") == Path("apps/bin")
    with pytest.raises(ValueError, match="Stage root escapes"):
        img._normalize_stage_root("../outside")

    missing = tmp_path / "missing.bin"
    img._copy_path(missing)
    assert "does not exist, skipping" in capsys.readouterr().out

    src_file = tmp_path / "src.bin"
    src_file.write_text("abc", encoding="utf-8")
    img._copy_path(src_file)
    assert (img.root / "src.bin").is_file()

    src_dir = tmp_path / "srcdir"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "child1").write_text("x", encoding="utf-8")
    (src_dir / "child2.txt").write_text("x", encoding="utf-8")
    (src_dir / "nested").mkdir()
    img._copy_path(src_dir)
    assert (img.root / "child1").is_file()
    assert (img.root / "child2.txt").is_file()
    assert not (img.root / "nested").exists()

    weird = tmp_path / "weird"
    try:
        os.mkfifo(weird)
        img._copy_path(weird)
        assert "not a file or directory, skipping" in capsys.readouterr().out
    except (AttributeError, PermissionError, OSError):
        pass

    executable = img.root / "child1"
    executable.write_bytes(b"x" * 70000)
    rows = img.entries()
    names = [name for name, _, _ in rows]
    assert names == sorted(names)
    row_map = {name: line for name, line, _ in rows}
    assert "K" in row_map["child1"]
    assert "x" in row_map["child1"]
    assert row_map["child2.txt"].startswith("-rw-")

    # stage artifacts (no directory support)
    stage_file = tmp_path / "stage.bin"
    stage_file.write_text("s", encoding="utf-8")
    stage_dir = tmp_path / "stage-dir"
    stage_dir.mkdir(parents=True, exist_ok=True)
    (stage_dir / "a.bin").write_text("a", encoding="utf-8")
    (stage_dir / "subdir").mkdir()
    img.stage_artifacts(
        [
            (tmp_path / "nope", Path("ignored")),
            (stage_file, Path("dest.bin")),
            (stage_dir, Path("tree")),
        ],
        stage_root="/apps",
    )
    assert (img.root / "dest.bin").is_file()
    assert (img.root / "a.bin").is_file()
    weird_stage = tmp_path / "weird-stage"
    try:
        os.mkfifo(weird_stage)
        img.stage_artifacts([(weird_stage, Path("w"))], stage_root="/apps")
        assert "not a file or directory, skipping" in capsys.readouterr().out
    except (AttributeError, PermissionError, OSError):
        pass

    # stage artifacts with directory support
    img_dirs = image.Image("y", supports_directories=True)
    img_dirs.stage_artifacts([(stage_file, Path("bin/d.bin")), (stage_dir, Path("apps/tree"))], stage_root="/root")
    assert (img_dirs.root / "root/bin/d.bin").is_file()
    assert (img_dirs.root / "root/apps/tree/a.bin").is_file()


def test_image_paths_cannot_escape_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt")
    img = image.Image("tf", supports_directories=True)
    img.root.mkdir(parents=True)
    monkeypatch.setattr(img, "ls", lambda args: 0)

    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("keep", encoding="utf-8")
    outside_dir = tmp_path / "outside-dir"
    outside_dir.mkdir()
    (outside_dir / "keep.txt").write_text("keep", encoding="utf-8")

    assert img.rm(["../outside.txt"]) == 1
    assert img.rm([str(outside_file)]) == 1
    assert img.rm(["."]) == 1
    assert outside_file.read_text(encoding="utf-8") == "keep"
    assert img.root.is_dir()

    parent_link = img.root / "linked-dir"
    parent_link.symlink_to(outside_dir, target_is_directory=True)
    assert img.rm(["linked-dir/keep.txt"]) == 1
    assert (outside_dir / "keep.txt").is_file()

    file_link = img.root / "linked-file"
    file_link.symlink_to(outside_file)
    assert img.rm(["linked-file"]) == 0
    assert not file_link.exists()
    assert outside_file.read_text(encoding="utf-8") == "keep"

    dir_link = img.root / "linked-directory"
    dir_link.symlink_to(outside_dir, target_is_directory=True)
    rows = {name: is_dir for name, _line, is_dir in img.entries()}
    assert rows["linked-directory"] is False
    with pytest.raises(ValueError, match="Path escapes"):
        img.entries("linked-directory")

    symlink_root = image.Image("linked-root", supports_directories=True)
    symlink_root.root.symlink_to(outside_dir, target_is_directory=True)
    assert symlink_root.rm(["keep.txt"]) == 1
    assert (outside_dir / "keep.txt").is_file()

    assert "Path escapes tf image root" in capsys.readouterr().out


def test_image_staging_cannot_escape_or_follow_destination_symlinks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt")
    img = image.Image("tf", supports_directories=True)
    source = tmp_path / "source.bin"
    source.write_text("new", encoding="utf-8")
    outside = tmp_path / "outside"
    outside.mkdir()
    outside_file = outside / "target.bin"
    outside_file.write_text("keep", encoding="utf-8")

    assert img.stage_artifacts([(source, Path("target.bin"))], stage_root="../outside") == 1
    assert outside_file.read_text(encoding="utf-8") == "keep"

    assert img.stage_artifacts([(source, Path("../escaped.bin"))]) == 1
    assert not (tmp_path / "mnt" / "escaped.bin").exists()

    img.root.mkdir(parents=True, exist_ok=True)
    (img.root / "linked-dir").symlink_to(outside, target_is_directory=True)
    assert img.stage_artifacts([(source, Path("linked-dir/target.bin"))]) == 1
    assert outside_file.read_text(encoding="utf-8") == "keep"

    destination_link = img.root / "destination.bin"
    destination_link.symlink_to(outside_file)
    assert img.stage_artifacts([(source, Path("destination.bin"))]) == 1
    assert outside_file.read_text(encoding="utf-8") == "keep"

    add_source = tmp_path / "destination.bin"
    add_source.write_text("new", encoding="utf-8")
    assert img.add([str(add_source)]) == 1
    assert outside_file.read_text(encoding="utf-8") == "keep"


def test_image_command_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt")
    img = image.Image("x", supports_directories=False, create_usage="create [size]")

    assert img.add([]) == 1
    assert img.rm([]) == 1
    assert img.ls(["bad"]) == 1
    assert img.create([]) == 1
    assert img.help() == 0
    out = capsys.readouterr().out
    assert "Usage: zde image x <subcommand>" in out
    assert "create [size]" in out

    copied: list[Path] = []
    monkeypatch.setattr(img, "_copy_path", lambda p: copied.append(p))
    monkeypatch.setattr(img, "ls", lambda args: 0)
    assert img.add(["a", "b"]) == 0
    assert copied == [Path("a"), Path("b")]
    monkeypatch.setattr(img, "ls", image.Image.ls.__get__(img, image.Image))

    root = img.root
    root.mkdir(parents=True, exist_ok=True)
    (root / "f.bin").write_text("x", encoding="utf-8")
    (root / "d").mkdir(exist_ok=True)
    (root / "d" / "x").write_text("x", encoding="utf-8")
    assert img.rm(["missing", "f.bin", "d"]) == 0
    assert not (root / "f.bin").exists()
    assert not (root / "d").exists()

    (root / "a.bin").write_text("x", encoding="utf-8")
    assert img.ls([]) == 0
    assert "a.bin" in capsys.readouterr().out


def test_image_pack_create_pack_concat(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt")
    img = image.ImagePack("cf")

    calls: list[tuple[str, list[str]]] = []
    monkeypatch.setattr(img, "_tool", lambda name, args: calls.append((name, args)) or 0)
    assert img._pack(Path("/tmp/out.img"), [Path("/a"), Path("/b")], skip_hidden=False) == 0
    assert calls[-1] == ("pack", ["/tmp/out.img", "/a", "/b"])
    assert img._pack(Path("/tmp/out2.img"), [Path("/c")], skip_hidden=True) == 0
    assert calls[-1] == ("pack", ["--skip-hidden", "/tmp/out2.img", "/c"])
    assert img._concat(Path("/tmp/all.img"), [(0, Path("/k")), (0x4000, Path("/d"))]) == 0
    assert calls[-1] == ("concat", ["/tmp/all.img", "0x0", "/k", "0x4000", "/d"])

    monkeypatch.setattr(img, "_require_configured_tools", lambda: False)
    assert img.create([]) == 1
    monkeypatch.setattr(img, "_require_configured_tools", lambda: True)
    assert img.create(["64"]) == 1
    assert "Usage: zde image cf create" in capsys.readouterr().out

    monkeypatch.setattr(image, "require_deps", lambda deps: pytest.fail("CF must not require a disk tool"))

    img.path.parent.mkdir(parents=True, exist_ok=True)
    img.path.write_text("x", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert img.create([]) == 1
    assert img.path.exists()

    packed: list[tuple[Path, list[Path]]] = []

    def _pack(output, inputs, skip_hidden=False):
        packed.append((output, inputs))
        output.write_text("new image", encoding="utf-8")
        return 0

    monkeypatch.setattr(img, "_pack", _pack)
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert img.create([]) == 0
    assert packed[-1][0] != img.path
    assert packed[-1][0].parent.parent == img.path.parent
    assert packed[-1][1] == [img.root]
    assert img.path.read_text(encoding="utf-8") == "new image"

    packed_count = len(packed)
    assert img.create(["128"]) == 1
    assert len(packed) == packed_count


@pytest.mark.parametrize("image_type", ["cf", "tf"])
def test_image_create_yes_overwrites_without_prompt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, image_type: str
) -> None:
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt")
    monkeypatch.setattr(image, "require_deps", lambda deps: True)
    monkeypatch.setattr("builtins.input", lambda prompt="": pytest.fail("unexpected prompt"))
    if image_type == "cf":
        img = image.ImagePack(image_type)
        monkeypatch.setattr(img, "_require_configured_tools", lambda: True)

        def _build(output, inputs):
            output.write_text("new image", encoding="utf-8")
            return 0

        monkeypatch.setattr(img, "_pack", _build)
    else:
        img = image.ImageZealFS(image_type, "4096")
        monkeypatch.setattr(img, "_require_tools", lambda names: True)

        def _build(size, output):
            output.write_text("new image", encoding="utf-8")
            return 0

        monkeypatch.setattr(img, "_build_image", _build)
    img.path.parent.mkdir(parents=True, exist_ok=True)
    img.path.write_text("old image", encoding="utf-8")

    with confirmation_scope(True):
        assert img.create([]) == 0
    assert img.path.read_text(encoding="utf-8") == "new image"


@pytest.mark.parametrize("image_type", ["cf", "tf"])
def test_failed_image_replacement_preserves_existing_image(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, image_type: str
) -> None:
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt")
    monkeypatch.setattr(image, "require_deps", lambda deps: True)
    if image_type == "cf":
        img = image.ImagePack(image_type)
        monkeypatch.setattr(img, "_require_configured_tools", lambda: True)
        monkeypatch.setattr(img, "_pack", lambda output, inputs: 9)
    else:
        img = image.ImageZealFS(image_type, "4096")
        monkeypatch.setattr(img, "_require_tools", lambda names: True)
        monkeypatch.setattr(img, "_build_image", lambda size, output: 9)
    img.path.parent.mkdir(parents=True, exist_ok=True)
    img.path.write_text("working image", encoding="utf-8")

    with confirmation_scope(True):
        assert img.create([]) == 9

    assert img.path.read_text(encoding="utf-8") == "working image"
    assert not list(img.path.parent.glob(f".{img.path.name}.*"))


@pytest.mark.parametrize("chown_rc", [0, 7])
def test_image_restores_caller_ownership_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, chown_rc: int
) -> None:
    monkeypatch.setattr(image, "MNT_DIR", tmp_path)
    img = image.ImageZealFS("tf", "64")
    img.path.write_text("old image")
    uid, gid = os.getuid() + 1, os.getgid() + 1
    monkeypatch.setattr(image.os, "getuid", lambda: uid)
    monkeypatch.setattr(image.os, "getgid", lambda: gid)
    calls = []

    def build(output):
        output.write_text("new image")
        return 0

    def run(cmd):
        assert img.path.read_text() == "old image"
        assert Path(cmd[-1]).read_text() == "new image"
        assert cmd[:3] == ["sudo", "chown", f"{uid}:{gid}"]
        calls.append(cmd)
        return chown_rc

    monkeypatch.setattr(image, "run", run)
    assert img._build_and_publish(build) == chown_rc
    assert len(calls) == 1
    assert img.path.read_text() == ("old image" if chown_rc else "new image")
    assert not list(tmp_path.glob(".tf.img.*"))


@pytest.mark.parametrize("returncode", [0, 7])
def test_image_zdt_hides_success_and_shows_failure_output(tmp_path, monkeypatch, capsys, returncode):
    img = image.ImageZealFS("tf", "4096")
    streams = []

    def run(cmd, *, stdout, stderr):
        assert stdout is stderr
        stdout.write("import: change staged on temporary image\nChanges applied\n")
        stderr.write("zdt diagnostic\n")
        streams.append(stdout)
        return returncode

    monkeypatch.setattr(image, "run", run)
    assert img._zdt(["import", "source", "/file"]) == returncode
    output = capsys.readouterr().out
    if returncode:
        assert "zdt diagnostic" in output
        assert "import: change staged" in output
    else:
        assert output == ""
    assert streams[0].closed


@pytest.mark.parametrize("colored", [False, True])
@pytest.mark.parametrize("returncode,diagnostic", [(0, ""), (7, "Disk full\nNo space left"), (7, "")])
def test_image_zdt_copy_status(tmp_path, monkeypatch, capsys, returncode, diagnostic, colored):
    monkeypatch.setattr("mods.cli.colors_enabled", lambda stdout=None: colored)
    img = image.ImageZealFS("tf", "4096")
    source = tmp_path / "hello.bin"

    def run(cmd, *, stdout, stderr):
        assert stdout is stderr
        stdout.write(diagnostic)
        return returncode

    monkeypatch.setattr(image, "run", run)
    assert img._zdt(["-i", "image.img", "import", str(source), "/hello.bin"], copying=source) == returncode
    output = capsys.readouterr().out
    prefix = f"  Copying file: {source} -> tf.img:/hello.bin ... "
    if returncode:
        message = "Disk full No space left" if diagnostic else "zdt exited with status 7"
        label = "\033[31m[FAIL]\033[0m" if colored else "[FAIL]"
        assert output == prefix + f'{label}: "{message}"\n'
    else:
        label = "\033[32m[OK]\033[0m" if colored else "[OK]"
        assert output == prefix + label + "\n"


@pytest.mark.parametrize("image_type,size,mbr", [("tf", "4096", True), ("eeprom", "32", False)])
def test_image_zdt_build_commands(tmp_path, monkeypatch, capsys, image_type, size, mbr):
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt with spaces")
    img = image.ImageZealFS(image_type, size)
    (img.root / "nested" / "empty").mkdir(parents=True)
    (img.root / "nested" / "file name").write_bytes(b"content")
    (img.root / ".hidden").write_bytes(b"hidden")
    (img.root / "filelink").symlink_to("nested/file name")
    (img.root / "dirlink").symlink_to("nested", target_is_directory=True)
    calls = []
    imported = {}

    def run(cmd, **kwargs):
        calls.append(cmd)
        assert cmd[1] == "--yes"
        assert cmd[0].endswith("/zdt")
        if "import" in cmd:
            imported[cmd[-1]] = Path(cmd[-2]).read_bytes()
        return 0

    monkeypatch.setattr(image, "run", run)
    assert img._build_image(size) == 0
    assert calls[0][2:] == ["image", "create", str(img.path), "--size", size + "KiB"] + (["--mbr"] if mbr else [])
    assert calls[1][2:] == ["-i", str(img.path), "partition", "create", "--alignment", "512B"]
    assert imported == {
        "/.hidden": b"hidden", "/filelink": b"content",
        "/dirlink/file name": b"content", "/nested/file name": b"content",
    }
    directories = [cmd[-1] for cmd in calls if "mkdir" in cmd]
    assert directories == ["/dirlink", "/dirlink/empty", "/nested", "/nested/empty"]
    assert not Path(next(cmd[-2] for cmd in calls if "import" in cmd)).exists()
    output = capsys.readouterr().out
    for destination in imported:
        assert f"-> {image_type}.img:{destination}" in output
    assert output.count("Copying file:") == len(imported)
    assert output.count("[OK]") == len(imported)


@pytest.mark.parametrize("image_type", ["tf", "eeprom"])
def test_image_zdt_empty_staging(tmp_path, monkeypatch, image_type):
    monkeypatch.setattr(image, "MNT_DIR", tmp_path)
    img = image.get_image(image_type)
    calls = []
    monkeypatch.setattr(image, "run", lambda cmd, **kwargs: calls.append(cmd) or 0)
    assert img._build_image(img.default_size) == 0
    assert img.root.is_dir()
    assert len(calls) == 2


def test_image_zdt_create_validation_and_dependencies(tmp_path, monkeypatch):
    monkeypatch.setattr(image, "MNT_DIR", tmp_path)
    img = image.ImageZealFS("tf", "4096")
    dependencies = []

    def require(deps):
        dependencies.append(deps)
        return True

    monkeypatch.setattr(image, "require_deps", require)
    monkeypatch.setattr(img, "_require_configured_tools", lambda: bool(dependencies))
    sizes = []

    def build(size, output):
        sizes.append(size)
        output.write_bytes(b"new image")
        return 0

    monkeypatch.setattr(img, "_build_image", build)
    for args in (["1", "2"], ["0"], ["-1"], ["1MiB"], ["abc"], ["1.5"], ["１２"], ["9" * 5000]):
        assert img.create(args) == 1
    assert dependencies == []
    assert img.create([]) == 0
    assert dependencies == [["Zeal8bit/Zeal-Disk-Tool"]]
    with confirmation_scope(True):
        assert img.create(["77"]) == 0
    assert sizes == ["4096", "77"]
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert img.create([]) == 1
    monkeypatch.setattr(image, "require_deps", lambda deps: False)
    assert img.create([]) == 1
    monkeypatch.setattr(image, "require_deps", require)
    monkeypatch.setattr(img, "_require_configured_tools", lambda: False)
    assert img.create([]) == 1


@pytest.mark.parametrize("image_type", ["tf", "eeprom"])
def test_image_zdt_skips_overlong_names(tmp_path, monkeypatch, capsys, image_type):
    monkeypatch.setattr(image, "MNT_DIR", tmp_path)
    img = image.ImageZealFS(image_type, "64")
    assets = img.root / "assets"
    assets.mkdir(parents=True)
    names = ["cards.tiled-project", "cards.gif", "1234567890123456", "12345678901234567", "é" * 8, "é" * 9]
    for name in names:
        (assets / name).write_text("asset")
    long_dir = img.root / "directory-too-long"
    long_dir.mkdir()
    (long_dir / "child").write_text("asset")
    copied = set()

    def run(cmd, **kwargs):
        if "import" in cmd:
            copied.add(cmd[-1])
        return 0

    monkeypatch.setattr(image, "run", run)
    assert img._build_image("64") == 0
    assert copied == {"/assets/cards.gif", "/assets/1234567890123456", "/assets/" + "é" * 8}
    assert all((assets / name).read_text() == "asset" for name in names)
    assert (long_dir / "child").is_file()
    assert "longer than 16 bytes" in capsys.readouterr().out


@pytest.mark.parametrize("failed_command", ["image", "partition", "mkdir", "import"])
def test_image_zdt_failure_preserves_output(tmp_path, monkeypatch, failed_command):
    monkeypatch.setattr(image, "MNT_DIR", tmp_path)
    monkeypatch.setattr(image, "require_deps", lambda deps: True)
    img = image.ImageZealFS("tf", "64")
    monkeypatch.setattr(img, "_require_configured_tools", lambda: True)
    (img.root / "dir").mkdir(parents=True)
    (img.root / "dir" / "file").write_bytes(b"new")
    img.path.write_bytes(b"old")
    calls = []

    def run(cmd, **kwargs):
        calls.append(cmd)
        if "image" in cmd:
            Path(cmd[4]).write_bytes(b"partial image")
        return 7 if failed_command in cmd else 0

    monkeypatch.setattr(image, "run", run)
    with confirmation_scope(True):
        assert img.create([]) == 7
    assert failed_command in calls[-1]
    assert img.path.read_bytes() == b"old"
    assert not list(tmp_path.glob(".tf.img.*"))
    imports = [cmd for cmd in calls if "import" in cmd]
    assert all(not Path(cmd[-2]).exists() for cmd in imports)


@pytest.mark.parametrize("bad_entry", ["cycle", "broken", "rootlink"])
def test_image_zdt_rejects_invalid_links(tmp_path, monkeypatch, capsys, bad_entry):
    monkeypatch.setattr(image, "MNT_DIR", tmp_path)
    img = image.ImageZealFS("tf", "64")
    if bad_entry == "rootlink":
        img.root.symlink_to(tmp_path, target_is_directory=True)
    else:
        img.root.mkdir()
        (img.root / bad_entry).symlink_to("." if bad_entry == "cycle" else "missing")
    monkeypatch.setattr(image, "run", lambda cmd, **kwargs: 0)
    assert img._build_image("64") == 1
    assert "Failed to populate" in capsys.readouterr().out


@pytest.mark.parametrize("image_type,size,mbr", [("tf", "4096", True), ("eeprom", "32", False)])
def test_image_zdt_real_roundtrip(tmp_path, monkeypatch, capfd, image_type, size, mbr):
    zdt = shutil.which("zdt") or str(image.ImageZealFS._TOOLS["zdt"].path)
    if not Path(zdt).is_file():
        pytest.skip("zdt is unavailable")
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt with spaces")
    monkeypatch.setattr(image, "require_deps", lambda deps: True)
    monkeypatch.setattr(image.ImageZealFS, "_TOOLS", {"zdt": ToolSpec(Path(zdt), required=True)})
    img = image.get_image(image_type)
    (img.root / "dir" / "empty").mkdir(parents=True)
    (img.root / "dir" / ".hidden").write_bytes(b"hidden")
    (img.root / "dir" / "star*?.bin").write_bytes(b"literal wildcard name")
    (img.root / "dir" / "file name").write_bytes(b"content")
    (img.root / "linked").symlink_to("dir", target_is_directory=True)
    assert img.create([]) == 0
    output = capfd.readouterr()
    assert output.out.count("[OK]") == 6
    assert "change staged" not in output.out + output.err
    assert "Changes applied" not in output.out + output.err
    missing = tmp_path / "missing.bin"
    assert img._zdt(["-i", str(img.path), "import", str(missing), "/missing.bin"], copying=missing) == 1
    output = capfd.readouterr().out
    assert '[FAIL]: "' in output
    assert "missing.bin" in output
    assert img.path.stat().st_size == int(size) * 1024
    assert img.path.stat().st_uid == os.getuid()
    metadata = json.loads(subprocess.check_output([zdt, "--json", "-i", str(img.path), "info"]))["data"]
    assert metadata["mbr"] is mbr
    assert metadata["partitions"][0]["start_lba"] == (1 if mbr else 0)
    exported = tmp_path / "exported"
    subprocess.run([zdt, "--yes", "-i", str(img.path), "export", "/", str(exported)], check=True)
    for directory in ("dir", "linked"):
        assert (exported / directory / "empty").is_dir()
        for name in (".hidden", "star*?.bin", "file name"):
            assert (exported / directory / name).read_bytes() == (img.root / directory / name).read_bytes()


def test_image_romdisk_config_and_create_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    mnt = tmp_path / "mnt"
    zos = tmp_path / "zos"
    monkeypatch.setattr(image, "MNT_DIR", mnt)
    monkeypatch.setattr(image, "ZOS_PATH", zos)
    img = image.ImageRomdisk()

    os_conf = zos / "os.conf"
    os_conf.parent.mkdir(parents=True, exist_ok=True)
    os_conf.write_text(
        """
        # comment
        CONFIG_A="quoted"
        CONFIG_B='single'
        CONFIG_ROMDISK_OFFSET_PAGES=2
        CONFIG_ROMDISK_INCLUDE_INIT_BIN=yes
        CONFIG_ROMDISK_IGNORE_HIDDEN=1
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    assert img._read_os_conf_value(os_conf, "CONFIG_A") == "quoted"
    assert img._read_os_conf_value(os_conf, "CONFIG_B") == "single"
    assert img._read_os_conf_value(os_conf, "CONFIG_MISSING") is None
    assert img._read_os_conf_value(zos / "missing.conf", "X") is None
    assert img._parse_conf_bool(None) is False
    assert img._parse_conf_bool("YES") is True

    monkeypatch.setattr(img, "_require_tools", lambda names: False)
    assert img.create([]) == 1
    monkeypatch.setattr(img, "_require_tools", lambda names: True)
    assert img.create(["bad"]) == 1

    # Missing kernel artifact
    assert img.create([]) == 1

    build = zos / "build"
    build.mkdir(parents=True, exist_ok=True)
    kernel_bin = build / "os.bin"
    artifact_conf = build / "os.conf"
    kernel_bin.write_bytes(b"x")

    # Missing stage dir
    assert img.create([]) == 1

    stage = mnt / "romdisk"
    stage.mkdir(parents=True, exist_ok=True)
    artifact_conf.write_text("CONFIG_ROMDISK_OFFSET_PAGES=oops\n", encoding="utf-8")
    assert img.create([]) == 1
    artifact_conf.write_text("CONFIG_ROMDISK_OFFSET_PAGES=0\n", encoding="utf-8")
    assert img.create([]) == 1

    kernel_bin.write_bytes(b"x" * 70000)
    artifact_conf.write_text("CONFIG_ROMDISK_OFFSET_PAGES=1\n", encoding="utf-8")
    assert img.create([]) == 1

    kernel_bin.write_bytes(b"x")
    artifact_conf.write_text(
        "CONFIG_ROMDISK_OFFSET_PAGES=2\nCONFIG_ROMDISK_INCLUDE_INIT_BIN=y\nCONFIG_ROMDISK_IGNORE_HIDDEN=on\n",
        encoding="utf-8",
    )
    os_conf.write_text("CONFIG_ROMDISK_OFFSET_PAGES=99\n", encoding="utf-8")
    disk_img = mnt / "romdisk.img"
    output_img = mnt / "roms" / "os_with_romdisk.img"
    latest = mnt / "roms" / "latest.img"
    output_img.parent.mkdir(parents=True, exist_ok=True)
    disk_img.write_bytes(b"old disk")
    output_img.write_bytes(b"old combined")
    latest.write_bytes(b"old default")

    def _pack_fail(output, inputs, skip_hidden=False):
        output.write_bytes(b"partial disk")
        return 5

    monkeypatch.setattr(img, "_pack", _pack_fail)
    assert img.create([]) == 5
    assert disk_img.read_bytes() == b"old disk"
    assert output_img.read_bytes() == b"old combined"
    assert latest.read_bytes() == b"old default"
    assert "CONFIG_ROMDISK_INCLUDE_INIT_BIN=y" in capsys.readouterr().out

    init_bin = zos / "build" / "romdisk" / "init" / "build" / "init.bin"
    init_bin.parent.mkdir(parents=True, exist_ok=True)
    init_bin.write_bytes(b"i")
    def _pack_success(output, inputs, skip_hidden=False):
        output.write_bytes(b"new disk")
        return 0

    def _concat_fail(output, parts):
        output.write_bytes(b"partial combined")
        return 6

    monkeypatch.setattr(img, "_pack", _pack_success)
    monkeypatch.setattr(img, "_concat", _concat_fail)
    assert img.create([]) == 6
    assert disk_img.read_bytes() == b"old disk"
    assert output_img.read_bytes() == b"old combined"
    assert latest.read_bytes() == b"old default"

    concat_parts: list[list[tuple[int, Path]]] = []

    def _concat_success(output, parts):
        concat_parts.append(parts)
        output.write_bytes(b"new combined")
        return 0

    monkeypatch.setattr(img, "_concat", _concat_success)
    assert img.create([]) == 0
    assert disk_img.read_bytes() == b"new disk"
    assert output_img.read_bytes() == b"new combined"
    assert len(concat_parts) == 1
    assert concat_parts[0][0] == (0x0000, kernel_bin)
    assert concat_parts[0][1][0] == 0x8000
    assert latest.is_symlink()
    assert latest.readlink() == Path("os_with_romdisk.img")
    assert latest.read_bytes() == b"new combined"
    out = capsys.readouterr().out
    assert "Created" in out


def test_image_registry_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    cf = image.get_image("cf")
    assert cf.image_type == "cf"
    assert cf.create_usage == "create"
    assert cf.default_create_size is None
    with pytest.raises(ValueError, match="Unknown image type"):
        image.get_image("nope")
    all_images = image.images()
    assert any(img.image_type == "romdisk" for img in all_images)

    class _Fake:
        def entries(self, relative_dir):
            return [("a", "line", False)]

    monkeypatch.setattr(image, "get_image", lambda image_type: _Fake())
    assert image.image_entries("anything", "x") == [("a", "line", False)]
