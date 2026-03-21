from __future__ import annotations

import os
from pathlib import Path
import stat

import pytest

from mods import image
from mods.tooling import ToolSpec


def test_image_path_helpers_copy_entries_and_stage(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    mnt = tmp_path / "mnt"
    monkeypatch.setattr(image, "MNT_DIR", mnt)

    img = image.Image("x", supports_directories=False)
    assert img._normalize_stage_root(None) == Path(".")
    assert img._normalize_stage_root(" ") == Path(".")
    assert img._normalize_stage_root("/") == Path(".")
    assert img._normalize_stage_root("/apps/bin") == Path("apps/bin")

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


def test_image_pack_create_pack_concat(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    assert img.create(["1", "2"]) == 1

    monkeypatch.setattr(image, "require_deps", lambda deps: False)
    assert img.create([]) == 1
    monkeypatch.setattr(image, "require_deps", lambda deps: True)

    img.path.parent.mkdir(parents=True, exist_ok=True)
    img.path.write_text("x", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert img.create([]) == 1
    assert img.path.exists()

    packed: list[tuple[Path, list[Path]]] = []
    monkeypatch.setattr(img, "_pack", lambda output, inputs, skip_hidden=False: packed.append((output, inputs)) or 0)
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    assert img.create([]) == 0
    assert packed[-1][0] == img.path
    assert packed[-1][1] == [img.root]
    assert not img.path.exists()

    assert img.create(["128"]) == 0


def test_image_zealfs_build_and_create(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(image, "MNT_DIR", tmp_path / "mnt")
    zealfs = tmp_path / "zealfs"
    zealfs.write_text("bin", encoding="utf-8")
    monkeypatch.setattr(image.ImageZealFS, "_TOOLS", {"zealfs": ToolSpec(zealfs, required=True)})

    tf = image.ImageZealFS("tf", "4096")
    calls: list[list[str]] = []
    returns = [3, 0, 4, 0, 0, 0]

    def _run(cmd):
        calls.append(cmd)
        return returns.pop(0)

    monkeypatch.setattr(image, "run", _run)
    assert tf._build_image("64") == 3
    assert tf._build_image("64") == 4
    assert tf._build_image("64") == 0
    assert any("--mbr" in cmd for cmd in calls)

    ee = image.ImageZealFS("eeprom", "32")
    monkeypatch.setattr(image, "run", lambda cmd: 0)
    assert ee._build_image("32") == 0

    monkeypatch.setattr(tf, "_require_tools", lambda names: False)
    assert tf.create([]) == 1
    monkeypatch.setattr(tf, "_require_tools", lambda names: True)
    assert tf.create(["1", "2"]) == 1
    monkeypatch.setattr(image, "require_deps", lambda deps: False)
    assert tf.create([]) == 1
    monkeypatch.setattr(image, "require_deps", lambda deps: True)

    tf.path.parent.mkdir(parents=True, exist_ok=True)
    tf.path.write_text("x", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _: "n")
    assert tf.create([]) == 1
    monkeypatch.setattr("builtins.input", lambda _: "y")
    monkeypatch.setattr(tf, "_build_image", lambda size: 0 if size in {"4096", "77"} else 1)
    assert tf.create([]) == 0
    assert tf.create(["77"]) == 0


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
    kernel_bin.write_bytes(b"x")

    # Missing stage dir
    assert img.create([]) == 1

    stage = mnt / "romdisk"
    stage.mkdir(parents=True, exist_ok=True)
    os_conf.write_text("CONFIG_ROMDISK_OFFSET_PAGES=oops\n", encoding="utf-8")
    assert img.create([]) == 1
    os_conf.write_text("CONFIG_ROMDISK_OFFSET_PAGES=0\n", encoding="utf-8")
    assert img.create([]) == 1

    kernel_bin.write_bytes(b"x" * 70000)
    os_conf.write_text("CONFIG_ROMDISK_OFFSET_PAGES=1\n", encoding="utf-8")
    assert img.create([]) == 1

    kernel_bin.write_bytes(b"x")
    os_conf.write_text(
        "CONFIG_ROMDISK_OFFSET_PAGES=2\nCONFIG_ROMDISK_INCLUDE_INIT_BIN=y\nCONFIG_ROMDISK_IGNORE_HIDDEN=on\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(img, "_pack", lambda output, inputs, skip_hidden=False: 5)
    assert img.create([]) == 5
    assert "CONFIG_ROMDISK_INCLUDE_INIT_BIN=y" in capsys.readouterr().out

    init_bin = zos / "build" / "romdisk" / "init" / "build" / "init.bin"
    init_bin.parent.mkdir(parents=True, exist_ok=True)
    init_bin.write_bytes(b"i")
    monkeypatch.setattr(img, "_pack", lambda output, inputs, skip_hidden=False: 0)
    monkeypatch.setattr(img, "_concat", lambda output, parts: 6)
    assert img.create([]) == 6

    monkeypatch.setattr(img, "_concat", lambda output, parts: 0)
    assert img.create([]) == 0
    out = capsys.readouterr().out
    assert "Created" in out


def test_image_registry_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    assert image.get_image("cf").image_type == "cf"
    with pytest.raises(ValueError, match="Unknown image type"):
        image.get_image("nope")
    all_images = image.images()
    assert any(img.image_type == "romdisk" for img in all_images)

    class _Fake:
        def entries(self, relative_dir):
            return [("a", "line", False)]

    monkeypatch.setattr(image, "get_image", lambda image_type: _Fake())
    assert image.image_entries("anything", "x") == [("a", "line", False)]
