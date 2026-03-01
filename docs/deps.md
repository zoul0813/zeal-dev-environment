# `zde deps`

`deps` manages optional and required ZDE dependencies defined by the dependency catalog.

## Usage

```sh
zde deps list [category]
zde deps cats
zde deps info <id>
zde deps install <id> [id...]
zde deps update <id> [id...]
zde deps build <id> [id...]
zde deps stage <target> <id> [id...]
zde deps remove <id> [id...]
```

Running `zde deps` with no arguments prints help and then shows installed dependencies.

## Subcommands

- `list [category]`: show dependency state, aliases, and health. With a category, filter the list.
- `cats`: print available catalog categories.
- `info <id>`: print the full rendered metadata for one dependency.
- `install <id> [id...]`: install one or more dependencies.
- `update <id> [id...]`: update one or more installed dependencies.
- `build <id> [id...]`: run each dependency's build step.
- `stage <target> <id> [id...]`: copy dependency build artifacts into an image target.
- `remove <id> [id...]`: remove one or more dependencies.

## Dependency IDs And Aliases

- Commands accept either a dependency ID or a defined alias.
- Duplicate IDs in a single command are de-duplicated before execution.
- Unknown IDs fail fast.

## State Output

The list view marks dependencies with:

- `[x]`: installed
- `[ ]`: not installed
- `[?]`: missing required dependency or broken dependency chain

State strings include values such as `ok`, `required-miss`, `broken(...)`, `untracked`, or `-`.

## Staging Targets

`stage` forwards to each dependency's stage logic. Supported image targets are the same targets used by `zde image`, such as:

- `eeprom`
- `cf`
- `tf`
- `romdisk`

## Notes

- Required dependencies are usually handled by `zde update`.
- Optional dependencies are installed only when you request them.
