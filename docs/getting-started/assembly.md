# Your First Assembly Program

ZDE provides two pure-assembly workflows: z88dk-z80asm and GNU AS. Both produce Zeal 8-bit OS binaries, but their source syntax is different and files cannot be copied between them unchanged.

Complete the [ZDE installation and shell setup](./README.md) first, then choose either workflow below.

## z88dk-z80asm

Create a project:

```sh
zde create zealos-z88dk --name hello-z88dk
cd hello-z88dk
```

The generated `src/main.asm` demonstrates input, output, and clean program termination. Important parts include:

- `INCLUDE "zos_sys.asm"` loads Zeal 8-bit OS constants and syscall macros.
- `ORG 0x4000` places the program at the address expected by Zeal 8-bit OS.
- `S_WRITE3(...)`, `READ()`, and `WRITE()` call operating-system services.
- `EXIT()` returns control to Zeal 8-bit OS. Every program must reach an exit path.

Build the project:

```sh
zde cmake
```

The executable raw binary is:

```text
build/hello-z88dk.bin
```

The starter asks for a name and prints a greeting. Continue with [Run and Deploy](./run.md) to test it.

## GNU AS

Return to the directory where you keep Zeal projects, then create a GNU AS project:

```sh
zde create zealos-gnuas --name hello-gnu
cd hello-gnu
```

The generated `src/main.asm` shows the GNU AS form of a Zeal 8-bit OS program:

- `.include "zos_sys.asm"` loads Zeal 8-bit OS constants and syscall macros.
- `.text` selects the code section, which the linker places at `0x4000`.
- `.global _start` exports the program entry point.
- `S_WRITE3 ...` calls the Zeal 8-bit OS write service.
- `EXIT()` returns control to Zeal 8-bit OS.

Build the project:

```sh
zde cmake
```

The executable raw binary is:

```text
build/hello-gnu.bin
```

The build also produces `build/hello-gnu`, an ELF file used during linking and debugging. Use the `.bin` file with Zeal 8-bit OS.

## Syntax at a Glance

| Purpose | z88dk-z80asm | GNU AS |
| --- | --- | --- |
| Include Zeal 8-bit OS macros | `INCLUDE "zos_sys.asm"` | `.include "zos_sys.asm"` |
| Program placement | `ORG 0x4000` | `.text` plus the linker script |
| Export a symbol | Assembler label | `.global symbol` plus label |
| Define text | `DEFM "text"` | `.ascii "text"` |
| Reserve bytes | `DEFS count` | `.space count` |
| Macro arguments | Usually parentheses and commas | Usually spaces and commas |

Choose the syntax used by the libraries or examples you want to follow. Do not mix directives from the two assemblers in one source file.

## Edit and Rebuild

Edit `src/main.asm`, then rebuild from the project directory:

```sh
zde cmake
```

## Troubleshooting

- Confirm the template matches the syntax: `zealos-z88dk` for z88dk-z80asm or `zealos-gnuas` for GNU AS.
- Check directive spelling and macro-call syntax when the assembler reports an unexpected token.
- Make sure every successful path reaches `EXIT()`.
- If an old build directory used another assembler, remove that project’s `build` directory and run `zde cmake` again.

## Next Steps

- Test the binary with [Run and Deploy](./run.md).
- Use the generated Zeal 8-bit OS syscall examples as the starting point for input and output.
- For an SDCC project containing both languages, follow [Mixed C and Assembly](./mixed.md).
