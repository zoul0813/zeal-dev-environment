# `zde cmake`

`cmake` is a thin wrapper around `cmake -B` and `cmake --build`.

## Usage

```sh
zde cmake
zde cmake out
zde cmake build --target all
```

## Behavior

- Uses `build` as the default build directory.
- If the first argument does not start with `-`, it is treated as the build directory name.
- If the build directory does not exist, ZDE runs:

```sh
cmake -B <build-dir>
```

- Then it runs:

```sh
cmake --build <build-dir> [extra args...]
```

## Examples

- `zde cmake`: configure into `build/` if needed, then build it.
- `zde cmake out`: configure into `out/` if needed, then build it.
- `zde cmake build --target clean`: pass extra flags through to `cmake --build`.
