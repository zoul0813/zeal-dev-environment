# Your First C Program

This guide creates and builds a Zeal 8-bit OS program in C using SDCC. Complete the [ZDE installation and shell setup](./README.md) first.

## Create the Project

From the directory where you keep your Zeal projects, run:

```sh
zde create zealos-sdcc --name hello-c
cd hello-c
```

ZDE creates a complete starter project. The important files are:

- `src/main.c`: the program source.
- `CMakeLists.txt`: the build definition and selected toolchain.
- `.vscode/settings.json`: optional editor configuration.

## Read the Program

The generated `src/main.c` contains:

```c
#include <stdio.h>

int main(void) {
    printf("Hello Zeal OS!\n");

    return 0;
}
```

`printf` writes to Zeal 8-bit OS standard output. Returning from `main` exits the program and returns control to the operating system.

## Build the Program

Run this command from the project directory:

```sh
zde cmake
```

ZDE configures the project, compiles it with SDCC, and writes the executable raw binary to:

```text
build/hello-c.bin
```

The build directory also contains intermediate files such as `hello-c.ihx` and `hello-c.map`. Transfer or run the `.bin` file.

## Edit and Rebuild

Change the message in `src/main.c`, save the file, and run the same build command again:

```sh
zde cmake
```

You do not need to recreate the project after changing its source.

## Run the Program

Continue with [Run and Deploy](./run.md) to test `build/hello-c.bin` in the Zeal Native Emulator or copy it to physical Zeal hardware.

## Troubleshooting

- If `zde` is not found, finish the [shell environment setup](../env.md) and open a new terminal.
- If ZDE cannot connect to Docker or Podman, start the container runtime and retry.
- If `hello-c` already exists, choose another project name or enter the existing directory. ZDE does not overwrite projects.
- If an old build directory was configured with another toolchain, remove that project’s `build` directory and run `zde cmake` again.

## Next Steps

- Add more `.c` files to the target in `CMakeLists.txt`.
- Learn how to [combine C and assembly](./mixed.md).
- Review the [`zde cmake` reference](../cmake.md).
