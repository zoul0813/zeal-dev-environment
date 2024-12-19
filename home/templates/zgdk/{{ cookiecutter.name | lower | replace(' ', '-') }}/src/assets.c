#include <stdio.h>
#include <zvb_gfx.h>
#include "assets.h"

gfx_error load_palette(gfx_context* ctx) {
    // Load the palette
    const size_t palette_size = &_palette_end - &_palette_start;
    return gfx_palette_load(ctx, &_palette_start, palette_size, 0);
}

gfx_error load_tileset(gfx_context* ctx, gfx_tileset_options* options) {
    const size_t size = &_tileset_end - &_tileset_start;
    return gfx_tileset_load(ctx, &_tileset_start, size, options);
}

void __assets__(void) __naked {
    __asm__(
        // shared palette
        "__palette_start:\n"
        "    .incbin \"assets/tileset.ztp\"\n"
        "__palette_end:\n"

        // tiles
        "__tileset_start:\n"
        "    .incbin \"assets/tileset.zts\"\n"
        "__tileset_end:\n");
}