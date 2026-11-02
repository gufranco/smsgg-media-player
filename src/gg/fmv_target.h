#ifndef FMV_TARGET_H
#define FMV_TARGET_H

#include "SMSlib.h"
#include "fmv/types.h"
#include "fmv/vdpcopy.h"

typedef u16 fmv_colour;
#define FMV_CRAM_ENTRY_BYTES 2u
#define FMV_COLOUR_BLACK     0x0000u
#define FMV_COLOUR_WHITE     0x0FFFu
#define FMV_COLOUR_RED       0x000Fu
#define FMV_MENU_PANEL  0x0100u
#define FMV_MENU_INK    0x0FFFu
#define FMV_MENU_ACCENT 0x019Fu
#define FMV_MENU_DIM    0x0766u
#define FMV_COLOUR_ASSERT    0x0F00u
#define FMV_KEYS_TEXT        "1 restarts 2 stops Start pauses Up mutes Down diag Left/Right seek"

#define FMV_SPRITE_PALETTE   16u

static inline void fmv_set_colour(u8 entry, fmv_colour colour)
{
    fmv_vdp_write((u16)((u16)entry * FMV_CRAM_ENTRY_BYTES), FMV_VDP_CRAM_WRITE,
                  (const u8 *)&colour, (u8)FMV_CRAM_ENTRY_BYTES);
}

static inline void fmv_set_bg_colour(u8 entry, fmv_colour colour)
{
    fmv_set_colour(entry, colour);
}

static inline void fmv_set_sprite_colour(u8 entry, fmv_colour colour)
{
    fmv_set_colour((u8)(entry + FMV_SPRITE_PALETTE), colour);
}

#endif
