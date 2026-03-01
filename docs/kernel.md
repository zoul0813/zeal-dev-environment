# `zde kernel`

`kernel` builds the Zeal kernel through `home/kernel.sh`.

## Usage

```sh
zde kernel
zde kernel <config>
zde kernel user
zde kernel menuconfig
```

## Behavior

- With no arguments, uses the `zeal8bit` kernel config.
- With a single argument, forwards that config name to `kernel.sh`.

## Special Modes

### `zde kernel user`

- Looks for `~/.zeal8bit/os.conf`.
- If found, copies it into `home/Zeal-8-bit-OS/os.conf` before the build.
- If the user config does not exist yet, ZDE warns and allows the build to create one.
- After a successful run, ZDE saves the resulting `os.conf` back to `~/.zeal8bit/os.conf`.

### `zde kernel menuconfig`

- If `~/.zeal8bit/os.conf` exists, ZDE preloads it before launching the menuconfig flow.
- After a successful run, ZDE persists the resulting config back to `~/.zeal8bit/os.conf`.

## Notes

- `user` and `menuconfig` are implemented as explicit subcommands, but any other argument is treated as a direct kernel config name.
