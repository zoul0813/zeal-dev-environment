# `zde -i`

`-i` opens an interactive shell inside a ZDE container.

## Usage

```sh
zde -i
zde -i -b
```

## What It Does

- Starts an interactive `/bin/bash` session in the configured container service.
- Mounts the current launch directory into the container as `/src`.
- Passes host UID, GID, and selected ZDE environment values into the container.

## Variants

- `zde -i`: opens the default development container.
- `zde -i -b`: opens the build service container defined by `ZDE_BUILD_SERVICE`, or falls back to the default service if that service is not present.

## When To Use It

- You want a full ZDE shell instead of a single forwarded command.
- You need to inspect the mounted project under `/src`.
