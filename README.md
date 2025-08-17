# Zeal Development Environment

## Setup

Add ZDE to your PATH

```shell
export ZDE_PATH="/path/to/ZDE"
export PATH="$PATH:$ZDE_PATH"
```

Once you've added ZDE to your path, you can then run `zde update` to
pull down all the necessary submodules, and get to the latest state.

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

* `update` - pulls the latest ZDE updates, along with associated Zeal repos

* `status` - shows the current status (running, mounted to, with docker/podman)

* `start` - start ZDE, mounting the current directory as the project root (ie; /src)

* `stop` - stop ZDE

* `restart` - restarts ZDE in the current directory

* `make` - execute make, passing all additional arguments (ie; `zde make all`)

  > You can pass additional arguments to `zde make`, such as `zde make all` or `zde make clean`, etc.

* `emu[lator]` - launches the Zeal Web Emulator at (http://127.0.0.1:1145/?r=latest)

  > You can optionally pass `stop` and `start` to stop or start the emulator.
  >
  > In addition, you can pass a URL encoded query string to pass additional arguments to the emulator,
  > such as the preferred ROM to use (default: `r=latest`).  Refer to the Zeal-WebEmulator docs for
  > available options.

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

### `zde create` example
  ```shell
  $ cd /path/to/root
  $ zde create zealos name=hello
  $ cd hello
  $ zde restart
  $ zde make
  $ zde emu
  ```
  The project will produce a `{project_name}.bin`, so in the case of the example you would have `hello.bin`
  to run in the emulator.


## Included Features

Zeal Dev Environment includes the following Zeal features

* [Zeal-8-bit-OS](home/Zeal-8-bit-OS)
* [Zeal-Bootloader](home/Zeal-Bootloader)
* [Zeal-VideoBoard-SDK](home/Zeal-VideoBoard-SDK)
* [ZealFS](home/ZealFS)
* [Zeal-WebEmulator](home/Zeal-WebEmulator)
* [zeal-game-dev-kit](home/zeal-game-dev-kit)

Refer to the indiivdual feature documentation for more details.
