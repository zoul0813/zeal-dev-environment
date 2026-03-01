# TUI vs CLI

The TUI and CLI use the same underlying command modules, but they are optimized for different kinds of work.

## When The TUI Is Better

The TUI is better when you want:

- guided discovery of available commands
- a browsable dependency list
- grouped config editing
- image file browsing without typing paths
- modal prompts instead of remembering exact argument syntax

It is especially useful for exploratory or occasional workflows.

## When The CLI Is Better

The CLI is better when you want:

- scripting or automation
- exact control over command arguments
- direct use of host-only wrapper commands
- quick one-off commands you already know
- features that are not exposed in a TUI workflow

## Practical Differences

### Command Coverage

- The TUI covers the ZDE commands only.
- The CLI covers both ZDE commands and host-only wrapper commands.

### Arguments

- The CLI accepts arbitrary argument lists.
- The TUI usually offers predefined actions and modal choices instead of free-form argument entry.

Examples:

- `zde deps list <category>` in CLI becomes a filter chooser in the TUI.
- `zde deps stage <target> <id>` in CLI becomes a dependency selection plus a target picker in the TUI.
- `zde create <template> --name <name> [extra args...]` in CLI becomes a template picker plus project-name prompt in the TUI.

### Image Management

- The CLI supports the full `image` command set, including `add`, `rm`, `ls`, and `create`.
- The TUI currently focuses on browsing and removing staged files; it does not expose the full image creation flow.

### Output Handling

- The CLI writes directly to stdout/stderr.
- The TUI may show output in status lines or modals, and may temporarily suspend itself while external commands run.

### Error Handling

- CLI failures return normal command exit codes immediately.
- TUI failures are surfaced as inline error statuses, captured text views, or command output before returning you to the interface.

## Rule Of Thumb

Use the TUI for navigation and guided workflows. Use the CLI for automation, advanced arguments, and full feature coverage.
