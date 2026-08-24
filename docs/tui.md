# `zde tui`

`tui` launches the optional Textual-based terminal UI.

Detailed TUI documentation is available in the [ZDE TUI Guide](./tui/README.md).

## Usage

```sh
zde tui
```

## Behavior

- Loads ZDE config before startup.
- If `output.color` is explicitly set to `off`, it exports `NO_COLOR=1`.
- Starts `mods.tui.app.ZDEApp` inside a managed runtime mode.

## Requirement

- Requires the Python `textual` package.

If Textual is missing, ZDE prints:

- `The optional TUI requires Textual.`
- `Install with: pip install textual`

## Related Config

- `textual.theme`: sets the configured theme name for the TUI.

## See Also

- [ZDE TUI Guide](./tui/README.md)
- [Navigation And Shortcuts](./tui/navigation.md)
- [TUI Screens And Features](./tui/screens.md)
- [TUI vs CLI](./tui/cli-differences.md)
