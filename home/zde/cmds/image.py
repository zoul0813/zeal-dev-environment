from __future__ import annotations

from mods import image as image_mod
from mods.tui.contract import ActionSpec, CommandSpec


def _dispatch(image: image_mod.Image, args: list[str]) -> int:
    if not args:
        return image.help()

    subcmd = args[0]
    subargs = args[1:]
    if subcmd in {"help", "-h", "--help"}:
        return image.help()
    if subcmd == "add":
        return image.add(subargs)
    if subcmd == "rm":
        return image.rm(subargs)
    if subcmd == "ls":
        return image.ls(subargs)
    if subcmd == "create" and image.create_usage is not None:
        return image.create(subargs)

    print(f"Unknown subcommand: {subcmd}")
    return image.help()


def _register_dynamic_subcommands() -> None:
    for image in image_mod.images():
        image_type = image.image_type

        def _subcmd(args: list[str], _image_type: str = image_type) -> int:
            return _dispatch(image_mod.get_image(_image_type), args)

        _subcmd.__name__ = f"subcmd_{image_type}"
        globals()[_subcmd.__name__] = _subcmd


_register_dynamic_subcommands()


def _sorted_images() -> list[image_mod.Image]:
    return sorted(image_mod.images(), key=lambda image: image.image_type)


def help() -> int:
    print("Usage: zde image <subcommand> [args]")
    print("Subcommands:")
    for image in _sorted_images():
        if image.create_usage is None:
            print(f"  {image.image_type} <add|rm|ls> [args]")
        else:
            print(f"  {image.image_type} <add|rm|ls|create> [args]")
    return 0


def main(args: list[str]) -> int:
    return help()


def get_tui_spec() -> CommandSpec:
    return CommandSpec(
        name="image",
        label="image",
        help="Manage and build EEPROM/CF/TF/ROMDISK images",
        actions=[
            ActionSpec(id="open", label="open", help="Open image media browser"),
        ],
    )


def get_tui_screen():
    from scrns.image_menu import ImageMenuScreen

    return ImageMenuScreen()
