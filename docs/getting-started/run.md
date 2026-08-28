# Run and Deploy a Program

Every getting-started workflow produces a raw `.bin` file that Zeal 8-bit OS can execute. This guide covers testing with the Zeal Native Emulator, transferring over UART, and placing a program on a microSD card.

## Find the Binary

For projects created by these guides, the executable is:

| Project | Raw Zeal 8-bit OS binary |
| --- | --- |
| C | `build/hello-c.bin` |
| z88dk-z80asm | `build/hello-z88dk.bin` |
| GNU AS | `build/hello-gnu.bin` |
| Mixed C and assembly | `build/hello-mixed.bin` |

If you chose another project name, use `build/<project-name>.bin`.

Zeal 8-bit OS needs the exact decimal byte count before receiving a binary over UART. From the project directory, run:

```sh
wc -c < build/hello-c.bin
```

Replace the filename with your binary. Use the number printed by this command; do not copy a size from an example because program sizes change when source or toolchain versions change.

## Test with the Zeal Native Emulator

Install [`Zeal Native Emulator`](https://github.com/Zeal8bit/Zeal-NativeEmulator) on your host computer and make sure its executable is available in `PATH`:

```sh
zeal-native --help
```

The emulator also needs a Zeal 8-bit OS ROM. Follow the emulator’s installation instructions to configure `~/.zeal8bit/roms/default.img`, or pass a ROM explicitly with `--rom`.

From the project directory, load the compiled program with:

```sh
zeal-native --uprog build/hello-c.bin
```

Replace `hello-c.bin` with your binary. The `--uprog` option loads the program into the ROM disk at the normal user-program address and starts it as the shell when Zeal 8-bit OS boots.

If no default ROM is configured, download or build `os_with_romdisk.img`, then pass its path explicitly:

```sh
zeal-native --rom /path/to/os_with_romdisk.img --uprog build/hello-c.bin
```

For the z88dk starter, enter a name when prompted. Other starter programs print their message and return to Zeal 8-bit OS.

Close the emulator window to stop it.

For command-line and debugger options, run:

```sh
zeal-native --help
```

## Transfer to Physical Hardware over UART

Connect the Zeal computer to the host through its UART adapter. Configure the serial terminal for:

- 57600 baud.
- 8 data bits, no parity, and 1 stop bit (8N1).
- Raw binary transfer with no text conversion or protocol framing.

Then:

1. Calculate the binary’s byte count with `wc -c` as shown above.
2. At the Zeal 8-bit OS prompt, enter `load <byte-count>`.
3. Use the host terminal’s raw-file send feature to send `build/<project-name>.bin`.
4. Wait until all bytes are transferred and confirm the program starts.

Follow the website’s [Zeal 8-bit Computer getting-started guide](https://zeal8bit.com/getting-started/) for current hardware connections and serial-terminal controls.

If loading fails, recalculate the size for the exact file being sent. Do not send the GNU AS ELF file named `build/hello-gnu`; send `build/hello-gnu.bin`.

## Put the Program on a microSD Card

ZDE can stage a binary and create a ZealFS microSD image. From the project directory, run:

```sh
zde image tf add build/hello-c.bin
zde image tf ls
zde image tf create
```

Replace `hello-c.bin` with your binary. The resulting image is written to:

```text
mnt/tf.img
```

Write that image to the microSD card using the method for your operating system, then insert the card into the Zeal computer. Follow the website’s [microSD card guide](https://zeal8bit.com/guides/sdcard/) for current partitioning and image-writing instructions.

At the Zeal 8-bit OS prompt, list the card contents and execute the program using its filename. Files ending in `.bin` are staged as executable by ZDE’s image tools.

To inspect, manage, or update files on an existing ZealFS-formatted card, use [Zeal Disk Tool](https://github.com/zeal8bit/Zeal-Disk-Tool). This is useful when you want to copy a newly compiled program onto a card without creating and writing a complete replacement image.

See the [`zde image` reference](../image.md) for staging, removal, image sizes, and other media targets.

## Troubleshooting

- If `zeal-native` is not found, install the Zeal Native Emulator and add its executable to `PATH`.
- If the emulator reports that no ROM is available, configure its default ROM or pass `--rom` as shown above.
- If the program does not start, confirm `--uprog` points to the raw `.bin` artifact.
- If `load` waits forever, confirm the terminal is sending a raw file and that the UART settings are 57600 baud, 8N1.
- If transfer ends too soon or too late, recalculate the exact binary size with `wc -c`.
- If `zde image tf create` reports a missing ZealFS dependency, run `zde update` and check `zde deps list`.
- If you only need to update an existing card, use Zeal Disk Tool instead of recreating the entire image.
- If Zeal 8-bit OS cannot execute a file, confirm you transferred the `.bin` artifact rather than an `.ihx`, `.map`, object, or ELF file.

## Continue Learning

- Return to the [workflow picker](./README.md#choose-your-workflow).
- Review the [C guide](./c.md), [assembly guide](./assembly.md), or [mixed guide](./mixed.md).
- Explore the complete [ZDE command reference](../README.md).
