# `zde image`

`image` manages file staging and image creation for ZDE media targets.

## Usage

```sh
zde image eeprom <subcommand> [args]
zde image cf <subcommand> [args]
zde image tf <subcommand> [args]
zde image romdisk <subcommand> [args]
```

Supported subcommands:

- `add <path1> [path2] [path3] ...`
- `rm <path1> [path2] [path3] ...`
- `ls`
- `create [size]` for `eeprom`, `cf`, and `tf`

`romdisk` supports `add`, `rm`, and `ls`, but not `create`.

## Targets

- `eeprom`: directory-backed staging plus ZealFS image creation.
- `cf`: directory-backed staging plus packed CompactFlash image creation.
- `tf`: directory-backed staging plus ZealFS image creation with MBR support.
- `romdisk`: staging-only target.

## Subcommand Details

### `add`

- Copies files into the target staging directory.
- If you pass a directory, only the top-level files are copied for this command path.
- Prints the updated target listing after the copy completes.

### `rm`

- Removes files or directories from the target staging directory.
- Prints the updated target listing after deletion.

### `ls`

- Lists staged entries in a compact permission and size view.

### `create`

- Requires dependency `Zeal8bit/ZealFS`.
- `eeprom` defaults to size `32`.
- `cf` defaults to size `64`.
- `tf` defaults to size `4096`.
- If the image file already exists, ZDE asks for confirmation before overwriting it.

## Legacy Alias

The old top-level command still works:

```sh
zde romdisk ...
```

It is internally redirected to:

```sh
zde image romdisk ...
```
