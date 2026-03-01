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

## Examples

```sh
zde create zealos --name hello
zde create zgdk --name breakout
zde create gh:org/template --name demo
```
