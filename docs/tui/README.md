# ZDE TUI Guide

This section documents the Textual-based ZDE terminal UI in more detail than the top-level [`zde tui`](../tui.md) command page.

## Contents

- [Overview](#overview)
- [What The TUI Covers](#what-the-tui-covers)
- [What The TUI Does Not Cover](#what-the-tui-does-not-cover)
- [Further Reading](#further-reading)

## Overview

The ZDE TUI is a menu-driven interface layered on top of the ZDE command modules. It is built with Textual and gives you a structured way to browse commands, select actions, inspect state, and complete common workflows without typing full command lines.

Unlike the CLI, the TUI is centered around:

- command selection
- action selection
- focused modal prompts
- item/action panels for stateful workflows such as dependencies, config, and image browsing

## What The TUI Covers

The TUI includes the ZDE command set, excluding `zde tui` itself.

Supported command areas:

- `cmake`
- `config`
- `create`
- `deps`
- `image`
- `kernel`
- `make`
- `update`

Commands are shown either:

- as simple command/action menus for direct execution
- or as custom TUI screens when a command defines a richer screen

## What The TUI Does Not Cover

The TUI does not replace the entire host wrapper.

Notably, it does not expose host-only commands such as:

- `zde emulator`
- `zde playground`
- `zde activate`
- `zde -i`

Those stay in the CLI because they are wrapper- and host-environment-driven.

## Further Reading

- [Navigation And Shortcuts](./navigation.md)
- [TUI Screens And Features](./screens.md)
- [TUI vs CLI](./cli-differences.md)
- [`zde tui` command reference](../tui.md)
