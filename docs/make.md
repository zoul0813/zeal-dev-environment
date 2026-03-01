# `zde make`

`make` forwards directly to `make` in the current project.

## Usage

```sh
zde make
zde make all
zde make clean
```

## Behavior

- Passes all arguments straight through to `make`.
- If `ASEPRITE_PATH` is set in the environment, ZDE first runs:

```sh
make -f /home/zeal8bit/zeal-game-dev-kit/aseprite.mk
```

- Then it runs the requested `make` command.

## When To Use It

- You want the normal project `Makefile` flow inside the ZDE environment.
- You want automatic Aseprite preprocessing when that tool is configured.
