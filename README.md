# Zeal Development Environment

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

Zeal Dev Environment (ZDE) is a collection of tools to simplify building projects for the [Zeal 8-bit Computer](https://zeal8bit.com/).

## Table of Contents

- [Setup](#setup)
- [Usage](#usage)
  - [General](#usage)
  - [Interactive Mode](#interactive-mode)
  - [Host Mode](#host-mode)
- [Features](#included-features)

## Setup

Clone the repo to your preffered location, such as ~/zeal-dev-environment

### Clone the repo

```shell
cd ~/

git clone https://github.com/zoul0813/zeal-dev-environment.git

cd zeal-dev-environment

# Run ZDE Update
./zde update
```

### Add ZDE to your PATH

Add ZDE to your PATH

```shell
export ZDE_PATH="/path/to/zeal-dev-environment"
export PATH="$PATH:$ZDE_PATH"
```

### Windows (WSL2)

If you experience issues in Windows, try the following:

* Install Git (https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-git)
* Install WSL2 (default is OK) to get an Ubuntu OS + bash shell (https://learn.microsoft.com/en-us/windows/wsl/install)
* Install Docker Desktop for Windows with the proper config for WSL2 (https://learn.microsoft.com/en-us/windows/wsl/tutorials/wsl-containers)
* `git -v clone https://github.com/zoul0813/zeal-dev-environment.git`, from the Bash shell, not PowerShell
* Follow ZDE Readme (https://github.com/zoul0813/zeal-dev-environment/blob/main/README.md)
* Type `zde update`

## Usage

```shell
zde COMMAND [OPTIONS]
```

### Commands

* `-i` - interactive mode, starts a new container mounting the current directory to `/src`

* `activate` - interactive mode, starts a new container mounting the current directory to `/src`

* `update` - pulls the latest ZDE updates, along with associated Zeal repos

* `status` - shows the current status (running, mounted to, with docker/podman)

* `start` - start ZDE, mounting the current directory as the project root (ie; /src)

* `stop` - stop ZDE

* `restart` - restarts ZDE in the current directory

* `make` - execute make, passing all additional arguments (ie; `zde make all`)

  > You can pass additional arguments to `zde make`, such as `zde make all` or `zde make clean`, etc.

* `cmake` - execute cmake in the current directory

  > You can optionally pass the name of the cmake build dir `zde cmake bin`, by default it assumes `build`

* `emu[lator]` - launches the Zeal Web Emulator at (http://127.0.0.1:1145/?r=latest)

  > You can optionally pass `stop` and `start` to stop or start the emulator.
  >
  > In addition, you can pass a URL encoded query string to pass additional arguments to the emulator,
  > such as the preferred ROM to use (default: `r=latest`).  Refer to the Zeal-WebEmulator docs for
  > available options.

* `playground` - launches the Zeal Playground at (http://127.0.0.1:1155/?r=latest)

  > You can optionally pass `stop` and `start` to stop or start the emulator.

* `image` - generates [eeprom,sd,cf] disk images from files contained within $ZDE_PATH/mnt/[eeprom,sd,cf]

  > This option copies the contents of $ZDE_PATH/mnt/[eeprom,sd,cf] into $ZDE_PATH/mnt/[eeprom,sd,cf].img
  >
  > You can optionally pass an additional "size" (32,64,etc) to create a 32k or 64k ZealFS image
  >
  > For example, `zde image eeprom 64` will copy the contents of >$ZDE_PATH/mnt/eeprom to
  > $ZDE_PATH/mnt/eeprom.img and create a 64k image file that can be flashed to the 64k EEPROM on Zeal 8-bit Computer.

* `rebuild` - rebuilds the ZDE docker image, this is for ZDE development and not something users should need to use

* `create` - creates a new project from available templates

  > Usage: `zde create {template} name={project_name}`
  >
  > Templates: `zealos`, `zgdk`
  >
  > The project template is created in the current working folder, so you will have a `project_name` folder in
  > your current path after executing.

### Interactive Mode

ZDE Interactive Mode allows you to shell into the ZDE container and run make/cmake/etc on your project

```shell
cd /path/to/project
zde -i
```

When using Interactive Mode, you have full access to the ZDE container system.

The modules provided by ZDE are located in `/home/zeal8bit`, and your project is mounted to `/src`.

### Host Mode

ZDE Host Mode allows you to use ZDE modules on your host, and sets up various env vars so you can run make/cmake
locally without needing to run a container.  This mode requires that you have all the necessary tooling already installed.

Follow the Zeal 8-bit [Getting Start Guide](https://github.com/Zeal8bit/Zeal-8-bit-OS/?tab=readme-ov-file#getting-started) to
setup your local environment with the necessary prerequisites.


To enable host mode in a shell, just source the `bin/activate` script
to setup your sessions env vars.

```shell
source $ZDE_PATH/bin/activate
```

This will export a handful of env vars used by Zeal build tools,
for example:

```shell
export ZDE_PATH="$ZDE_HOME/.."
export ZOS_PATH="$ZDE_HOME/Zeal-8-bit-OS"
export ZVB_SDK_PATH="$ZDE_HOME/Zeal-VideoBoard-SDK"
export ZGDK_PATH="$ZDE_HOME/zeal-game-dev-kit"
export ZAR_PATH="$ZDE_HOME/zeal-archiver"

export PATH="$ZDE_PATH:$PATH"
export PATH="$ZOS_PATH/tools:$PATH"
export PATH="$ZVB_SDK_PATH/tools/zeal2gif:$PATH"
export PATH="$ZVB_SDK_PATH/tools/tiled2zeal:$PATH"
export PATH="$ZDE_HOME/zeal-archiver:$PATH"
export PATH="$ZDE_PATH:$PATH"
```

Once you activate ZDE Host Mode, you can just run `make` in your project and ZOS_PATH, ZVB_SDK_PATH, ZGDK_PATH and
various other paths will be setup for you.

### `zde create` example
  ```shell
  $ cd /path/to/root
  $ zde create zealos name=hello
  $ cd hello
  $ zde make
  $ zde emu
  ```
  The project will produce a `{project_name}.bin`, so in the case of the example you would have `hello.bin`
  to run in the emulator.

### Use without Docker/Podman/Containers

You can activate ZDE by sourcing the `bin/activate` script.

```shell
source $ZDE_PATH/bin/activate
```

Optionally, add a `zde-activate` alias

```shell
alias zde-activate="source $ZDE_PATH/bin/activate"
```

Once you've added ZDE to your path, you can then run `zde update` to
pull down all the necessary submodules, and get to the latest state.

## Included Features

Zeal Dev Environment includes the following Zeal features

* [Zeal-8-bit-OS](home/Zeal-8-bit-OS)
* [Zeal-Bootloader](home/Zeal-Bootloader)
* [Zeal-VideoBoard-SDK](home/Zeal-VideoBoard-SDK)
* [ZealFS](home/ZealFS)
* [Zeal-WebEmulator](home/Zeal-WebEmulator)
* [zeal-game-dev-kit](home/zeal-game-dev-kit)
* [Zeal-Playground](home/Zeal-Playground)

Refer to the indiivdual feature documentation for more details.
