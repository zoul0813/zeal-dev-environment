#!/bin/sh
# Run inside a built ZDE image, with /opt toolchain binaries on PATH.
set -eu

smoke_dir=$(mktemp -d)
trap 'rm -rf "$smoke_dir"' EXIT HUP INT TERM
cd "$smoke_dir"

uname -m
# The tools must match the runtime's Python ELF architecture: emulation could
# otherwise hide an accidentally copied executable from the other platform.
python3 - <<'PYTHON'
from pathlib import Path
import struct
import sys


def machine(path):
    with Path(path).resolve().open("rb") as executable:
        header = executable.read(20)
    assert header[:4] == b"\x7fELF", f"Not an ELF executable: {path}"
    return struct.unpack_from("<H" if header[5] == 1 else ">H", header, 18)[0]


expected = machine(sys.executable)
for tool in ("/opt/sdcc/bin/sdcc", "/opt/z88dk/bin/zcc",
             "/opt/z88dk/bin/z88dk-z80asm", "/opt/gnu-as/bin/z80-elf-as"):
    assert machine(tool) == expected, f"Runtime/tool architecture mismatch: {tool}"
print("Host tool architectures match the runtime.")
PYTHON
printf 'int main(void) { return 42; }\n' > hello.c
sdcc -mz80 hello.c -o sdcc.ihx
test -s sdcc.ihx
zcc +zeal8bit hello.c -o zeal.bin
test -s zeal.bin
printf 'org 0\nld a,42\nret\n' > z88dk.asm
z88dk-z80asm -b z88dk.asm
test -s z88dk.bin
printf '.text\n.global _start\n_start:\nld a,42\nret\n' > gnu.s
z80-elf-as -o gnu.o gnu.s
z80-elf-ld -Ttext=0 -o gnu.elf gnu.o
z80-elf-objcopy -O binary gnu.elf gnu.bin
cmp z88dk.bin gnu.bin
printf 'SDCC, z88dk (Zeal target), and GNU binutils compile/link smoke tests passed.\n'
