# Mix C and Assembly

This guide adds one SDASZ80 assembly routine to an SDCC C project. It uses a function with no arguments or return value so the first example avoids more complex calling-convention details.

Complete the [C guide](./c.md) first if you have not built an SDCC project before.

## Create the Project

From the directory where you keep your Zeal projects, run:

```sh
zde create zealos-sdcc --name hello-mixed
cd hello-mixed
```

The `zealos-sdcc` template enables both C and SDASZ80 assembly. SDASZ80 syntax differs from the z88dk-z80asm and GNU AS syntax covered by the [pure assembly guide](./assembly.md).

## Add the Assembly Routine

Create `src/helper.asm` with this content:

```asm
    .module helper
    .globl _asm_step

    .area _CODE
_asm_step::
    nop
    ret
```

The routine performs one no-operation instruction, then returns to its C caller. `_asm_step` has a leading underscore because SDCC maps the C name `asm_step` to that assembly symbol.

## Call the Routine from C

Replace `src/main.c` with:

```c
#include <stdio.h>

extern void asm_step(void);

int main(void) {
    printf("Calling assembly...\n");
    asm_step();
    printf("Returned to C.\n");

    return 0;
}
```

The `extern` declaration tells the C compiler that another source file provides `asm_step`.

## Add the Assembly File to the Build

Find this line in `CMakeLists.txt`:

```cmake
add_executable(hello-mixed "src/main.c")
```

Add the assembly source to it:

```cmake
add_executable(hello-mixed "src/main.c" "src/helper.asm")
```

If you chose another project name, keep the target name generated in your file and only add `"src/helper.asm"`.

## Build the Program

Run:

```sh
zde cmake
```

The build output should show both a C object and an ASM object. The executable raw binary is:

```text
build/hello-mixed.bin
```

## Run the Program

Follow [Run and Deploy](./run.md). A successful run prints:

```text
Calling assembly...
Returned to C.
```

## Troubleshooting

- If `_asm_step` is undefined while linking, confirm `src/helper.asm` appears in `add_executable` and contains `.globl _asm_step`.
- If `asm_step` is undefined while compiling C, confirm the `extern void asm_step(void);` declaration appears before `main`.
- Use `.area _CODE` for executable SDASZ80 code in this example.
- Keep the leading underscore on the assembly symbol, but omit it from the C declaration and call.
- Remove the project’s `build` directory and run `zde cmake` again after changing toolchain-level build settings.

Passing parameters, returning values, preserving registers, and mixing larger routines require understanding the SDCC calling convention. Keep those concerns out of the first routine, then consult the SDCC documentation before expanding its interface.
