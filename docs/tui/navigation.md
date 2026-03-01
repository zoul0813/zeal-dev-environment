# TUI Navigation And Shortcuts

The ZDE TUI is keyboard-first. Most interaction happens through list navigation, `Enter`, `Esc`, arrow keys, and function-key shortcuts shown in the footer.

## Global Behavior

- The app opens on a command list.
- A current working directory bar is shown near the bottom.
- The footer updates to show available bindings for the current screen and visible actions.
- The current Textual theme is persisted when you change it.

## Command Menu

The first screen shows the available commands.

- Use arrow keys to move through commands.
- Press `Enter` to open a command.
- Press `Esc` to open a quit confirmation prompt.

If a command has only one action and no custom screen, the action runs immediately.

## Action Menus

Commands with multiple actions but no custom screen open an action list.

- Use arrow keys to choose an action.
- Press `Enter` to run it.
- Press `Esc` to go back to the command list.

## Item/Action Screens

The richer screens (`deps`, `config`, `create`, `image`) use a two-panel layout:

- left panel: items
- right panel: actions

Shared navigation:

- `Left`: focus the item list
- `Right`: focus the action list
- `Enter` on the item list: run the currently selected action for that item
- `Enter` on the action list: run the highlighted action
- `Esc`: go back
- `PageUp` / `PageDown`: page within the focused list

The active panel is highlighted, and the visible action list changes based on the selected item.

## Function-Key Shortcuts

The footer exposes context-sensitive function-key shortcuts for the actions currently available on the active screen.

Common examples:

- `F2`: refresh (on screens that support refresh)
- `F3`: open or info
- `F4`: edit or update
- `F5`: create or install
- `F6`: toggle or build
- `F7`: stage
- `F8`: remove or unset
- `F9`: filter

These are dynamic. The exact keys shown depend on the current screen and selected item.

## Modals

The TUI uses focused modal dialogs for confirmations and input:

- Confirm dialogs: `Y` confirms, `N` or `Esc` cancels, `Left` / `Right` move between buttons
- Prompt dialogs: `Enter` submits, `Esc` cancels
- Choice dialogs: `Enter` selects, `Esc` or `q` cancels
- Text/info viewers: `Esc` or `q` closes

## External Command Runs

When the TUI launches an external command, it temporarily suspends the interface and returns terminal control to the command output. After the command finishes, the TUI resumes and redraws the screen.

Some actions intentionally pause after running and wait for `Enter` before returning to the TUI.
