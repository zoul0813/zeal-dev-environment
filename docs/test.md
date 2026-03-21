# `zde test`

Run Python unit tests for ZDE code.

## Usage

```sh
zde test [pytest-args...]
```

## Behavior

- Runs `pytest` inside the ZDE container.
- With no arguments, runs the ZDE unit test suite:

```sh
zde test
# equivalent to:
pytest home/zde/tests
```

- Extra arguments are passed directly to pytest:

```sh
zde test -v
zde test -vv
zde test -k config
zde test -s
zde test --cov=home/zde/mods --cov-report=term-missing
```

## Common Flags

- `-v`: verbose output (shows test names)
- `-vv`: extra verbose output
- `-k <expr>`: run tests matching an expression
- `-s`: show stdout/stderr from tests (disable output capture)
- `--maxfail=1`: stop after first failure
- `--lf`: run only last-failed tests

## Notes

- This command is intended for ZDE's own Python tests (`home/zde/tests`).
- Existing non-test commands are unchanged.
