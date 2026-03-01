# `zde playground`

`playground` is a host-only service command that serves and opens the Zeal Playground UI.

## Usage

```sh
zde playground
zde playground start
zde playground stop
zde playground status
zde playground "r=latest"
```

## Actions

- `start`: build the playground manifest, start the service container, and open the browser.
- `stop`: stop and remove the playground service container.
- `status`: print whether the service is `running` or `stopped`.

If you pass anything other than `start`, `stop`, or `status`, ZDE treats it as a query string and opens:

```text
http://127.0.0.1:1155/?r=latest&<your-query>
```

## Requirements

- Optional dependency `Zeal8bit/Zeal-Playground` must be installed.

## Notes

- Before starting, ZDE rebuilds `files/manifest.json` for the playground content set.
- The service runs in a detached container named `zeal8bit-playground`.
