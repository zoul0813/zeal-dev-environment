# `zde emulator` / `zde emu`

`emulator` is a host-only service command that serves and opens the Zeal Web Emulator.

## Usage

```sh
zde emulator
zde emu
zde emulator start
zde emulator stop
zde emulator status
zde emulator "r=latest"
```

## Actions

- `start`: ensure the emulator dependency is installed, start the service container, and open the browser.
- `stop`: stop and remove the emulator service container.
- `status`: print whether the service is `running` or `stopped`.

If you pass anything other than `start`, `stop`, or `status`, ZDE treats it as a query string and opens:

```text
http://127.0.0.1:1145/?r=latest&<your-query>
```

## Requirements

- Optional dependency `Zeal8bit/Zeal-WebEmulator` must be installed.
- If it is missing, the command prints the exact `zde deps install ...` command to run.

## Notes

- The service runs in a detached container named `zeal8bit-emulator`.
- The current working directory is mounted into that service container as `/src`.
