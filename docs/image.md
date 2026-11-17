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
- `create [size]` for `eeprom` and `tf`
- `create` for `cf`
- `create` for `romdisk`

## Targets

- `eeprom`: directory-backed staging plus raw ZealFS v2 image creation using `zdt`.
- `cf`: directory-backed staging plus packed CompactFlash image creation.
- `tf`: directory-backed staging plus ZealFS v2 image creation using `zdt`, with an MBR.
- `romdisk`: staged file target plus ROM disk regeneration using the latest kernel image.

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

- Requires dependency `Zeal8bit/Zeal-Disk-Tool`.
- `eeprom` defaults to size `64`.
- `cf` and `romdisk` use the OS tools supplied by `Zeal8bit/Zeal-8-bit-OS`.
- Sizes for `eeprom` and `tf` are positive integers in KiB.
- `cf` uses the packed image format and does not accept a size argument.
- `tf` defaults to `4096` (4 MiB), with the first partition starting at sector 1.
- `eeprom` and `tf` skip file and directory names longer than ZealFS's 16-byte limit, including their subtrees, and print a warning. Staged files remain unchanged; rename an excluded entry before creating the image if it is needed.
- If the image file already exists, ZDE asks for confirmation before overwriting it.
- Created images belong to the user running ZDE (`HOST_UID`/`HOST_GID`, which default to the host user's UID/GID). TF/EEPROM creation writes image files directly through `zdt`.
- TF/EEPROM creation includes staged directory trees, empty directories, hidden files, and symlink targets. Directory symlink cycles or unreadable sources fail the build.
- A failed build preserves the previous image. Images are replaced atomically after successful creation and population.
- Pass `-y` or `--yes` to `zde image ... create` to confirm overwriting without a prompt.
- `romdisk create`:
  - Packs staged files from `mnt/romdisk` into `mnt/romdisk.img`.
  - Uses `home/Zeal-8-bit-OS/build/os.bin` and its matching `build/os.conf` to rebuild `mnt/roms/os_with_romdisk.img`.
  - Atomically updates `mnt/roms/latest.img` to select the regenerated image used by the default emulator launch.

## Legacy Alias

The old top-level command still works:

```sh
zde romdisk ...
```

It is internally redirected to:

```sh
zde image romdisk ...
```
