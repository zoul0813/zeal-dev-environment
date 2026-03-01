# `zde activate`

`activate` is a host-only command. It prints shell exports so you can use ZDE-managed toolchains without entering the container.

## Usage

```sh
eval "$(zde activate)"
```

If you run `zde activate` directly in an interactive terminal, the wrapper prints a reminder to use `eval`.

## What It Does

- Emits environment variables for the current shell session.
- Loads ZDE base paths.
- Loads dependency-specific exports from `~/.zeal8bit/deps.env`.
- Lets you run local `make`, `cmake`, and toolchain binaries directly on the host.

## When To Use It

- You already have the required host tooling installed.
- You want to build locally instead of through the container wrapper.
- You want installed dependency tools added to `PATH`.
