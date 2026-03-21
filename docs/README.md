# ZDE Command Reference

This directory documents the current command surface for the Zeal Development Environment (ZDE) as implemented in this repository.

ZDE has two execution layers:

- The host wrapper at `./zde`, which selects a container runtime, manages long-lived browser services, and forwards most commands into the container.
- The ZDE command router at `home/zde/zde.py`, which provides the main command modules such as `deps`, `image`, `create`, and `config`.

## Contents

- [Quick Start](#quick-start)
- [Host Commands](#host-commands)
- [ZDE Commands](#zde-commands)
- [Notes](#notes)
- [Examples](#examples)
- [Runtime Configuration](#runtime-configuration)
- [Container Runtime Selection](#container-runtime-selection)
- [Compose And Image Defaults](#compose-and-image-defaults)
- [Host Environment Variables](#host-environment-variables)

## Quick Start

Typical setup flow:

```sh
./zde update
./zde deps list
./zde create zealos --name hello
cd hello
./zde make
./zde emulator
```

## Host Commands

- [`activate`](./activate.md): emit shell exports for host mode.
- [`-i`](./interactive.md): open an interactive shell inside the container.
- [`emulator` / `emu`](./emulator.md): run the Zeal Web Emulator service.
- [`playground`](./playground.md): run the Zeal Playground service.
- [`update`](./update.md): update the repo, pull the container image, and run ZDE sync tasks.
- [`rebuild`](./rebuild.md): reserved host command that is not implemented yet.

## ZDE Commands

- [`cmake`](./cmake.md): configure and build CMake projects.
- [`config`](./config.md): inspect and edit ZDE config values.
- [`create`](./create.md): scaffold a new project from a template.
- [`deps`](./deps.md): inspect, install, build, stage, update, and remove dependencies.
- [`image`](./image.md): manage EEPROM, CF, TF, and romdisk staging areas and image files.
- [`kernel`](./kernel.md): build the Zeal kernel with preset or user config.
- [`make`](./make.md): run `make` in the current project.
- [`test`](./test.md): run ZDE Python unit tests with pytest.
- [`tui`](./tui.md): launch the optional Textual interface.

## Notes

- Running `./zde help` or just `./zde` prints the ZDE command list and current service status.
- `romdisk` is kept as a legacy top-level alias, but it now routes to `zde image romdisk ...`.
- Most commands shown here can be invoked as `./zde ...` from the repo root or as `zde ...` if the wrapper is on your `PATH`.

### Examples

Use Podman and a custom state directory:

```sh
export ZDE_USE=podman
export ZDE_USER_PATH="$HOME/.config/zde"
zde update
```

Use a custom image tag:

```sh
export ZDE_VERSION=dev
zde deps list
```

Pin the full image reference directly:

```sh
export ZDE_IMAGE_REF="ghcr.io/example/zeal-dev-environment:feature-x"
zde -i
```

## Runtime Configuration

ZDE is configured primarily through host environment variables. The `./zde` wrapper reads these values before it chooses a container runtime or launches a command.

### Container Runtime Selection

By default, ZDE auto-detects the container runtime in this order:

1. `docker`
2. `podman`

You can force the runtime with `ZDE_USE`:

```sh
ZDE_USE=docker zde update
ZDE_USE=podman zde update
```

`ZDE_USE` only accepts `docker` or `podman`. Any other value is ignored and ZDE falls back to auto-detect.

If you want to pin the exact executable that should receive `compose` commands, set `CONTAINER_CMD` instead:

```sh
CONTAINER_CMD=docker zde deps list
CONTAINER_CMD=podman zde -i
```

If `CONTAINER_CMD` is set, it takes precedence over `ZDE_USE`.

### Compose And Image Defaults

The development container uses `docker-compose.yml`, which is invoked as:

```sh
$CONTAINER_CMD compose -f "$ZDE_PATH/docker-compose.yml" ...
```

The default compose service is configured with:

- service name `zeal8bit-dev-env`
- container image `zoul0813/zeal-dev-environment:latest`
- a bind mount of the current working directory as `/src`
- bind mounts for `./home`, `./mnt`, and the ZDE user state directory

Compose also loads:

- the repository `.env` file for container defaults
- `${ZDE_USER_PATH}/deps.env` for generated dependency exports

You normally should not edit `deps.env` by hand.

### Host Environment Variables

Common user-facing variables:

- `ZDE_PATH`: location of this repository. If unset, the wrapper derives it from the location of `./zde`.
- `ZDE_USE`: choose `docker` or `podman` for runtime auto-selection.
- `CONTAINER_CMD`: explicitly choose the executable used for container operations. This overrides `ZDE_USE`.
- `ZDE_IMAGE`: container image repository. Default: `zoul0813/zeal-dev-environment`.
- `ZDE_VERSION`: container image tag. Default: `latest`.
- `ZDE_IMAGE_REF`: full image reference override. Default: `${ZDE_IMAGE}:${ZDE_VERSION}`.
- `ZDE_USER_PATH`: host path for ZDE state files. Default: `$HOME/.zeal8bit`.
- `ZDE_BRANCH`: branch used by `zde update` when pulling the ZDE repository.
- `ZDE_STRICT_EXIT`: set to `1` to preserve non-zero exit codes in interactive terminals.

Command-specific variables:

- `CONTAINER_SERVICE`: default compose service for forwarded commands and `zde -i`.
- `ZDE_BUILD_SERVICE`: compose service used by `zde -i -b`.

Advanced overrides:

- `HOST_UID`: UID forwarded into the container.
- `HOST_GID`: GID forwarded into the container.
- `HOST_HOME`: host home directory value forwarded into the container.
- `LAUNCH_PWD`: host directory mounted as `/src` for long-lived service containers.
- `HOST_CWD`: working directory value forwarded into the container runtime environment.
