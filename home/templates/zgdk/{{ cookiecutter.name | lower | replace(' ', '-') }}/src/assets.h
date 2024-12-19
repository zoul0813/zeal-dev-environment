#include <stdint.h>
#include <zvb_gfx.h>

void __assets__(void);

extern uint8_t _palette_end;
extern uint8_t _palette_start;
extern uint8_t _tileset_end;
extern uint8_t _tileset_start;

gfx_error load_palette(gfx_context* ctx);
gfx_error load_tileset(gfx_context* ctx, gfx_tileset_options* options);
