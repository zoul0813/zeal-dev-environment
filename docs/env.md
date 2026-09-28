# Shell Environment Setup

Configure your shell so ZDE commands and editor support work from any Zeal project directory.

## Recommended Variables

Set these values in your shell startup file:

- `ZDE_PATH`: absolute path to your Zeal Development Environment checkout.
- `PATH`: include `$ZDE_PATH` so the `zde` command is available everywhere.

The ZDE wrapper can derive its repository location without `ZDE_PATH`. Exporting it is still recommended because generated VS Code settings use `${env:ZDE_PATH}` to locate ZDE’s forced-include header and ClangFormat configuration.

These examples assume ZDE was cloned to:

```text
$HOME/zeal-dev-environment
```

If you cloned it elsewhere, replace that value with its absolute path.

Do not copy or symlink only the `zde` wrapper into another directory. The wrapper loads scripts and configuration relative to its own location. Add the repository directory itself to `PATH`.

## Linux With Bash

Add these lines to `~/.bashrc`:

```sh
export ZDE_PATH="$HOME/zeal-dev-environment"
export PATH="$ZDE_PATH:$PATH"
```

Reload the configuration:

```sh
source "$HOME/.bashrc"
```

## Linux With Zsh

Add these lines to `~/.zshrc`:

```sh
export ZDE_PATH="$HOME/zeal-dev-environment"
export PATH="$ZDE_PATH:$PATH"
```

Reload the configuration:

```sh
source "$HOME/.zshrc"
```

## Linux With Fish

Set `ZDE_PATH` and add it to Fish’s persistent path:

```fish
set -Ux ZDE_PATH "$HOME/zeal-dev-environment"
fish_add_path "$ZDE_PATH"
```

## macOS

The default macOS shell is Zsh. Add these lines to `~/.zshrc`:

```sh
export ZDE_PATH="$HOME/zeal-dev-environment"
export PATH="$ZDE_PATH:$PATH"
```

Reload the configuration:

```sh
source "$HOME/.zshrc"
```

If you use Bash or Fish on macOS, follow the matching shell instructions above.

## Windows With WSL2

ZDE runs inside a WSL2 Linux shell, not PowerShell or Command Prompt. Clone ZDE inside the WSL filesystem, then configure the shell inside WSL.

For the default Bash shell, add these lines to `~/.bashrc`:

```sh
export ZDE_PATH="$HOME/zeal-dev-environment"
export PATH="$ZDE_PATH:$PATH"
```

Reload the configuration:

```sh
source "$HOME/.bashrc"
```

Do not add ZDE to the Windows system `PATH`; the `zde` wrapper is a Linux shell script and must run inside WSL.

## Verify Your Environment

Open a new terminal or reload your shell configuration, then run:

```sh
printf '%s\n' "$ZDE_PATH"
command -v zde
zde --version
```

`ZDE_PATH` should print your checkout’s absolute path. `command -v zde` should print the wrapper inside that checkout. You can now enter any Zeal project and run:

```sh
zde cmake
```

## VS Code

Generated projects reference `${env:ZDE_PATH}` for ZDE’s forced-include header and ClangFormat configuration. Restart VS Code after changing your shell environment, or launch a project from a configured terminal so VS Code inherits the variable:

```sh
code .
```

If VS Code was already open when you added `ZDE_PATH`, fully close and reopen it before troubleshooting unresolved editor paths.

## Host-Mode Environment

Normal container-based commands do not require host toolchain variables. Do not manually configure dependency variables such as `ZOS_PATH`, `ZVB_SDK_PATH`, or `ZGDK_PATH` for container use.

To intentionally use ZDE-managed dependencies directly on the host, activate them for the current shell:

```sh
eval "$(zde activate)"
```

Activation exports `ZDE_HOME`, `ZDE_PATH`, dependency variables, and their executable paths. It affects only the current shell session.

## Optional Overrides

These variables are not required for normal use:

- `ZDE_USE`: prefer `docker` or `podman` during runtime selection.
- `CONTAINER_CMD`: explicitly select the container command and override `ZDE_USE`.
- `ZDE_USER_PATH`: change the user-state directory from its `~/.zeal8bit` default.
- `ZDE_IMAGE`, `ZDE_VERSION`, or `ZDE_IMAGE_REF`: override the container image selection.
- `ZDE_BRANCH`: select the branch used by `zde update`.
- `ZDE_SOFT_EXIT`: translate failed host-wrapper commands to exit code 0 when set to `1`. Defaults to `0`.
- `ZDE_STRICT_EXIT`: force real command exit codes when set to `1`, overriding `ZDE_SOFT_EXIT`.

See the [runtime configuration reference](./README.md#runtime-configuration) for behavior and precedence.

## Troubleshooting

- If `ZDE_PATH` is empty, confirm you edited the startup file used by your current shell.
- If `command -v zde` prints nothing, confirm `$ZDE_PATH` is included in `PATH`.
- If VS Code cannot resolve `${env:ZDE_PATH}`, restart it or launch it from a configured terminal.
- If `zde --version` reports a container error, start Docker or Podman and retry.
- If you move the ZDE checkout, update `ZDE_PATH` in your shell startup file.
