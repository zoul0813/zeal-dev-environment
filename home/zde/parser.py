from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zde")
    sub = parser.add_subparsers(dest="command")

    make_p = sub.add_parser("make")
    make_p.add_argument("make_args", nargs=argparse.REMAINDER)

    cmake_p = sub.add_parser("cmake")
    cmake_p.add_argument("cmake_args", nargs=argparse.REMAINDER)

    kernel_p = sub.add_parser("kernel")
    kernel_p.add_argument("kernel_config", nargs="?")

    image_p = sub.add_parser("image")
    image_p.add_argument("image_type", choices=["eeprom", "cf", "tf"])
    image_p.add_argument("size", nargs="?")

    create_p = sub.add_parser("create")
    create_p.add_argument("create_args", nargs=argparse.REMAINDER)

    romdisk_p = sub.add_parser("romdisk")
    rom_sub = romdisk_p.add_subparsers(dest="romdisk_cmd")

    rom_add = rom_sub.add_parser("add")
    rom_add.add_argument("paths", nargs="+")

    rom_rm = rom_sub.add_parser("rm")
    rom_rm.add_argument("paths", nargs="+")

    rom_sub.add_parser("ls")

    emu_p = sub.add_parser("emu")
    emu_p.add_argument("mode", nargs="?", default="start", choices=["start", "stop"])
    emu_p.add_argument("query", nargs="?")

    emulator_p = sub.add_parser("emulator")
    emulator_p.add_argument("mode", nargs="?", default="start", choices=["start", "stop"])
    emulator_p.add_argument("query", nargs="?")

    pg_p = sub.add_parser("playground")
    pg_p.add_argument("mode", nargs="?", default="start", choices=["start", "stop"])
    pg_p.add_argument("query", nargs="?")

    sub.add_parser("activate")

    for name in ["update", "status", "start", "stop", "restart", "rebuild"]:
        sub.add_parser(name)

    return parser
