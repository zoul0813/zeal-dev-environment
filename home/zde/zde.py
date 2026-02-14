#!/usr/bin/env python3
"""ZDE in-container command router."""

from __future__ import annotations

import sys

from cmake import cmd_cmake
from common import HELP_TEXT
from create import cmd_create
from emulator import cmd_emulator, cmd_emulator_stop
from image import cmd_image
from kernel import cmd_kernel
from make import cmd_make
from parser import build_parser
from romdisk import cmd_romdisk_add, cmd_romdisk_ls, cmd_romdisk_rm
from shell import interactive_shell


HOST_ONLY_COMMANDS = {"update", "status", "start", "stop", "restart", "rebuild"}


def main(argv: list[str]) -> int:
    if not argv:
        print(HELP_TEXT)
        return 0

    if argv[0] == "-i":
        return interactive_shell()

    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "make":
        return cmd_make(args)
    if args.command == "cmake":
        return cmd_cmake(args)
    if args.command == "kernel":
        return cmd_kernel(args)
    if args.command == "image":
        return cmd_image(args)
    if args.command == "create":
        return cmd_create(args)
    if args.command == "romdisk":
        if args.romdisk_cmd == "add":
            return cmd_romdisk_add(args)
        if args.romdisk_cmd == "rm":
            return cmd_romdisk_rm(args)
        return cmd_romdisk_ls()
    if args.command in {"emu", "emulator"}:
        if args.mode == "stop":
            return cmd_emulator_stop("emulator")
        return cmd_emulator("emulator", args.query)
    if args.command == "playground":
        if args.mode == "stop":
            return cmd_emulator_stop("playground")
        return cmd_emulator("playground", args.query)

    if args.command == "activate":
        print('This command is host-only: use eval "$(zde activate)" from the host shell.')
        return 1

    if args.command in HOST_ONLY_COMMANDS:
        print(f"This command is host/container lifecycle management and is not supported in-container: {args.command}")
        return 1

    print(HELP_TEXT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
