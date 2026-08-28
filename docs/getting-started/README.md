# Getting Started with ZDE

Zeal Development Environment (ZDE) provides the compilers, assemblers, Zeal 8-bit OS headers, project templates, and supporting tools needed to build software for the [Zeal 8-bit Computer](https://zeal8bit.com/).

This guide takes you from installing ZDE to choosing a language workflow. The workflow guides then build a first program, and the shared run guide explains how to test it in an emulator or transfer it to physical hardware.

## What You Will Need

- Git.
- Docker or Podman with Compose support.
- Linux, macOS, or Windows with WSL2.
- A terminal running Bash, Zsh, or Fish.
- VS Code is optional.

Start your container runtime before running ZDE commands. Windows users must run ZDE inside WSL2, not PowerShell or Command Prompt.

## Install ZDE

Clone ZDE, enter the checkout, and run its initial update:

```sh
cd "$HOME"
git clone https://github.com/zoul0813/zeal-dev-environment.git
cd zeal-dev-environment
./zde update
```

`zde update` pulls the development container and synchronizes required dependencies, including Zeal 8-bit OS.

## Configure Your Shell

Set `ZDE_PATH` to the checkout and add it to `PATH`. This makes `zde` available inside any user project and lets generated VS Code settings find ZDE editor support files.

For a checkout at `~/zeal-dev-environment`, Bash and Zsh use:

```sh
export ZDE_PATH="$HOME/zeal-dev-environment"
export PATH="$ZDE_PATH:$PATH"
```

Add these lines to your shell startup file so they remain available in new terminals. See [Shell Environment Setup](../env.md) for Linux, macOS, WSL2, Fish, VS Code, and optional environment overrides.

## Verify ZDE

Open a new terminal or reload your shell configuration, then run:

```sh
printf '%s\n' "$ZDE_PATH"
command -v zde
zde --version
zde create -t
zde deps list
```

Expected results:

- `ZDE_PATH` prints the absolute path to your ZDE checkout.
- `command -v zde` finds the wrapper inside that checkout.
- `zde --version` prints the ZDE and container-image versions.
- `zde create -t` lists the bundled project templates.
- `zde deps list` shows required and optional dependency state.

If a ZDE command reports a container connection error, start Docker or Podman and retry.

## Keep Projects Outside the ZDE Checkout

Create a separate directory for your own software. ZDE mounts the current project directory into its development container.

```sh
mkdir -p "$HOME/zeal-projects"
cd "$HOME/zeal-projects"
```

Keeping application projects outside the ZDE checkout prevents generated source files and build artifacts from becoming part of the environment repository.

## Choose Your Workflow

Choose the route matching what you want to write:

| Goal | Language and toolchain | ZDE template | Detailed guide |
| --- | --- | --- | --- |
| Write a Zeal OS program in C | C with SDCC | `zealos-sdcc` | `c.md` |
| Write a Zeal OS program in assembly | Assembly with z88dk-z80asm | `zealos-z88dk` | `assembly.md` |
| Use GNU assembler syntax | Assembly with GNU AS | `zealos-gnuas` | `assembly.md` |
| Combine C and assembly | C with SDCC and assembly with SDASZ80 | `zealos-sdcc` | `mixed.md` |
| Build a graphics-focused game | C with ZGDK and the Zeal Video Board SDK | `zgdk` | Advanced next step; see [`zde create`](../create.md) |

If you are unsure, start with the C workflow. It provides the shortest path from a generated project to a working Zeal OS binary.

The detailed workflow pages are being added after this top-level guide. Their filenames are stable so other ZDE and website documentation can link to them as they are completed.

## Documentation Map

This directory contains the beginner learning path:

- `README.md`: installation, shell setup, verification, and workflow selection.
- `c.md`: first Zeal OS C program using SDCC.
- `assembly.md`: first assembly program using either z88dk-z80asm or GNU AS.
- `mixed.md`: calling an SDASZ80 assembly routine from SDCC C.
- `run.md`: locating build artifacts, emulator testing, UART transfer, and SD-card deployment.

Command reference material remains one level above this directory:

- [Shell environment](../env.md)
- [`zde create`](../create.md)
- [`zde cmake`](../cmake.md)
- [`zde deps`](../deps.md)
- [`zde emulator`](../emulator.md)
- [`zde image`](../image.md)

## Shared Conventions

- Run project commands from the generated project directory.
- Use `zde cmake` to configure and compile every CMake-based tutorial project.
- Use the template named by your chosen workflow; assembler syntaxes are not interchangeable.
- Treat `zde activate` as optional host mode. Normal tutorials run through the container wrapper.
- Test in an emulator before transferring to physical hardware when possible.

## Updating ZDE

Run this from any directory after shell setup:

```sh
zde update
```

See the [`zde update` reference](../update.md) for branch selection, image updates, and dependency synchronization behavior.

## Getting Help

- Review the [ZDE command reference](../README.md).
- Review the [Zeal 8-bit Computer website](https://zeal8bit.com/).
- Ask questions in the [Zeal 8-bit Discord community](https://zeal8bit.com/discord).
