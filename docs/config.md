# `zde config`

`config` manages persistent ZDE settings stored in `~/.zeal8bit/zde.conf.yml`.

## Usage

```sh
zde config
zde config list
zde config get <key>
zde config set <key> <value>
zde config unset <key>
```

Running `zde config` with no arguments is the same as `zde config list`.

## Supported Keys

- `deps.rename-bins`: when staging dependency artifacts, rename `.bin` files to remove the extension.
- `deps.skip-sync-installed`: skip git sync for already-installed dependencies during update.
- `output.color`: force ANSI colors on or off; when unset, ZDE auto-detects.
- `textual.screenshot-scale`: scale factor for native TUI screenshot previews (`1.0` = default size).
- `textual.theme`: theme name for the optional Textual UI.

## Value Rules

- Boolean keys accept `on/off`, `true/false`, `yes/no`, or `1/0`.
- `textual.screenshot-scale` accepts any numeric value greater than `0`.
- `output.color` displays as `on`, `off`, or `auto` when unset.
- String values must be non-empty.

## Examples

```sh
zde config set output.color off
zde config get output.color
zde config unset output.color
zde config set textual.theme monokai
zde config set textual.screenshot-scale 1.25
```
