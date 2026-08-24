# `zde create`

`create` scaffolds a new project from a local template or any template source accepted by Cookiecutter.

## Usage

```sh
zde create <template> --name <project-name> [extra cookiecutter args...]
zde create -t
```

## Behavior

- Lists local templates with `zde create -t`.
- Uses a local template directory when the template name matches a folder under `home/templates/`.
- Otherwise passes the template argument directly to `cookiecutter`.
- Writes generated projects into `/src`, which maps to your current host working directory.
- Refuses to overwrite an existing target directory.

## Name Handling

- `--name <value>` is the preferred syntax.
- `--name=<value>` is also supported.
- Legacy `name=<value>` is still accepted.
- If no name is provided, ZDE prompts interactively.

## Requirements

- Requires `cookiecutter` to be installed in `PATH` or at `/opt/penv/bin/cookiecutter`.

## Local Templates

- `zealos`: Zeal OS C starter using SDCC, with application metadata and a `bin/` output directory.
- `zealos-sdcc`: minimal Zeal OS C starter using SDCC.
- `zealos-z88dk`: Zeal OS assembly starter using z88dk-z80asm syntax.
- `zealos-gnuas`: Zeal OS assembly starter using GNU AS syntax.
- `zgdk`: Zeal Game Dev Kit starter using SDCC, ZGDK, and the Zeal Video Board SDK.

The `zgdk` template requires its optional dependency set. Install it before building a generated game project:

```sh
zde deps install zgdk
```

## Examples

```sh
zde create zealos-sdcc --name hello
zde create zealos-z88dk --name hello-asm
zde create zgdk --name breakout
zde create gh:org/template --name demo
```
