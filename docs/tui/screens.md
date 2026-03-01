# TUI Screens And Features

The ZDE TUI mixes generic command runners with custom screens for workflows that benefit from browsing and structured input.

## Generic Command Runner

Commands without a custom screen are shown as simple command or action menus.

This applies to straightforward command modules such as:

- `cmake`
- `make`
- `update`
- `kernel` subcommands when used through the inferred action list

The TUI discovers subcommands automatically and renders them as actions when a module does not provide a custom screen.

## Dependency Manager Screen

The `deps` screen is the richest TUI workflow.

Features:

- color-coded dependency list
- state markers (`[x]`, `[ ]`, `[?]`)
- dependency info modal
- category filter picker
- install, update, build, stage, and remove actions
- automatic action visibility based on each dependency's capabilities

TUI-only conveniences:

- `filter` opens a category chooser instead of requiring a typed category name
- `stage` opens a target picker before running the stage action
- `info` opens a scrollable modal instead of printing to the terminal

Build actions temporarily suspend the UI and then prompt for `Enter` before returning.

## Configuration Screen

The `config` screen presents config keys grouped by namespace instead of a flat CLI key list.

Features:

- grouped view by top-level section (such as `deps` or `output`)
- inline display of current value
- visual distinction between default and explicit values
- `edit`, `toggle`, and `unset` actions based on key type and state

Behavior differences:

- boolean values are edited through a choice dialog
- string values are edited through a prompt dialog
- `unset` is only shown when a key is explicitly set

## Create Project Screen

The `create` screen provides a template picker and project-name prompt.

Features:

- browse local templates
- prompt for the new project directory name
- inline success status
- scrollable failure output modal when create fails

This screen is focused on local template creation and the project name prompt.

## Image Browser

The `image` screen is a browser for staged image targets.

Top-level features:

- pick a media target: `eeprom`, `cf`, `tf`, or `romdisk`
- open a file-tree style browser for that target

Inside the file browser:

- navigate into directories
- move up with `..`
- remove files or directories with confirmation
- refresh the listing

This screen is a staged-file browser, not a full replacement for every `zde image` CLI subcommand.

## App-Level Features

Across all screens, the TUI also provides:

- a persistent current working directory display
- status lines for success, warning, and error feedback
- contextual footer shortcuts
- saved theme preference through `textual.theme`

If your Textual environment exposes system commands such as theme switching, theme changes are persisted by ZDE. The built-in screenshot system command is intentionally hidden.
