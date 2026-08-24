# Zeal Development Environment

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

Zeal Development Environment (ZDE) is the build and tooling environment for working on software for the [Zeal 8-bit Computer](https://zeal8bit.com/). It provides a consistent containerized toolchain, project scaffolding, dependency management, image staging utilities, and optional host-mode activation.

See the [ZDE command reference](./docs/README.md) for detailed command documentation.

## Table of Contents

- [What ZDE Provides](#what-zde-provides)
- [Getting Started](#getting-started)
- [Linux](#linux)
- [macOS](#macos)
- [Windows (WSL2)](#windows-wsl2)
- [Environment Variables](#environment-variables)
- [Quick Command Overview](#quick-command-overview)
- [Requirements And Dependencies](#requirements-and-dependencies)
- [Upgrading from a Previous Version](#upgrading-from-a-previous-version)

## What ZDE Provides

- A container-based development environment for Zeal projects.
- A host wrapper script (`./zde`) for launching builds, tools, and long-lived services.
- Optional host-mode activation for running against the ZDE-managed toolchain without entering the container.
- Project templates for quickly starting new Zeal applications.
- Dependency management for required and optional tool repositories.

## Getting Started

Clone the repository into a stable location and run the initial update:

```sh
cd "$HOME"
git clone https://github.com/zoul0813/zeal-dev-environment.git
cd zeal-dev-environment
./zde update
```

ZDE does not require environment variables for normal container-based use. Setting `ZDE_PATH` is still recommended because generated VS Code settings use it to find ZDE editor support files. Add that directory to your shell’s `PATH` so you can run commands such as `zde cmake` from any project directory.

See [Shell Environment Setup](./docs/env.md) if you cloned ZDE somewhere else, use another shell, or need troubleshooting help.

### Linux

Install `git` and a supported container runtime, then add this line to `~/.bashrc`:

```sh
export ZDE_PATH="$HOME/zeal-dev-environment"
export PATH="$ZDE_PATH:$PATH"
```

Reload the shell configuration and verify ZDE:

```sh
source "$HOME/.bashrc"
command -v zde
zde --version
```

If you use Zsh, put the export in `~/.zshrc` and source that file instead. Ensure your user can run the selected container runtime.

### macOS

Install `git` and a container runtime. Docker Desktop and Podman are supported. Start the runtime, then add this line to `~/.zshrc`:

```sh
export ZDE_PATH="$HOME/zeal-dev-environment"
export PATH="$ZDE_PATH:$PATH"
```

Reload the shell configuration and verify ZDE:

```sh
source "$HOME/.zshrc"
command -v zde
zde --version
```

### Windows (WSL2)

Use ZDE from a Linux shell inside WSL2, not from PowerShell or Command Prompt. Clone ZDE inside the WSL filesystem and follow the Linux installation commands above.

For the default Bash shell, add this line to `~/.bashrc` inside WSL:

```sh
export ZDE_PATH="$HOME/zeal-dev-environment"
export PATH="$ZDE_PATH:$PATH"
```

Then reload and verify:

```sh
source "$HOME/.bashrc"
command -v zde
zde --version
```

Docker Desktop with WSL2 integration and Podman are supported runtime options.

## Environment Variables

No ZDE-specific environment variable is required for normal container-based use. The wrapper derives its repository path, state directory, image, and container runtime defaults automatically.

You should still export `ZDE_PATH` with the absolute path to the ZDE checkout. Generated VS Code settings use `${env:ZDE_PATH}` to locate ZDE’s forced-include header and ClangFormat configuration. Adding `$ZDE_PATH` to `PATH` also makes the `zde` command available from any project directory.

Other environment variables such as `ZDE_USER_PATH`, `ZDE_USE`, and `ZDE_IMAGE_REF` are optional overrides. See the [runtime configuration reference](./docs/README.md#runtime-configuration) for details.

`zde activate` is optional host mode. It exports ZDE and dependency paths for users who intentionally run toolchains on the host instead of through the container wrapper.

## Quick Command Overview

Use `zde COMMAND [args]`.

Host wrapper and service commands:

- `zde -v` / `zde --version`: print the current ZDE version and configured ZDE image reference.
- [`zde update`](./docs/update.md): update the local ZDE checkout, pull the container image, and run ZDE sync tasks.
- [`zde -i`](./docs/interactive.md): open an interactive shell inside the ZDE container.
- [`zde activate`](./docs/activate.md): emit shell exports for host mode.
- [`zde emulator`](./docs/emulator.md): start, stop, or query the Zeal Web Emulator service.
- [`zde playground`](./docs/playground.md): start, stop, or query the Zeal Playground service.

Core ZDE commands:

- [`zde deps`](./docs/deps.md): manage required and optional dependencies.
- [`zde create`](./docs/create.md): scaffold a new project from a template.
- [`zde make`](./docs/make.md): run `make` in the current project.
- [`zde cmake`](./docs/cmake.md): configure and build CMake projects.
- [`zde image`](./docs/image.md): manage EEPROM, CF, TF, and romdisk staging and image files.
- [`zde config`](./docs/config.md): inspect and change persistent ZDE config.
- [`zde kernel`](./docs/kernel.md): build the Zeal kernel with predefined or user config.
- [`zde tui`](./docs/tui.md): launch the optional terminal UI.
- [`zde test`](./docs/test.md): run ZDE Python unit tests.

For the full command map, runtime configuration, and per-command reference pages, see [docs/README.md](./docs/README.md).

## Requirements And Dependencies

Base requirements:

- `git`
- a supported container runtime
- a working container runtime with compose support

ZDE dependency model:

- Required dependencies are installed and synchronized by `zde update`.
- Optional dependencies are installed on demand with `zde deps install <id-or-alias>`.
- Installed dependency state is tracked in `~/.zeal8bit/deps-lock.yml`.
- Generated dependency environment exports are written to `~/.zeal8bit/deps.env`.
- The state directory defaults to `~/.zeal8bit` and can be overridden by setting `ZDE_USER_PATH` in your environment before running `zde`.

Host mode:

- You can activate ZDE without entering the container by running `eval "$(zde activate)"` or sourcing `bin/activate`.
- Host mode assumes you already have the required native tooling available on your machine.

Project-specific prerequisites may still apply depending on which Zeal project, SDK, or optional dependency you are using.

## Upgrading from a Previous Version

If you are on an older ZDE version, run `zde update` twice — the first run pulls the latest ZDE code, and the second applies any updated sync tasks against the new version:

```sh
./zde update
./zde update
```

ZDE will automatically migrate required (core) dependencies. Non-core optional dependencies are no longer tracked as submodules — they can be reinstalled after upgrading with `zde deps install <id-or-alias>`.
