#include "fmv/screen.h"

#include "SMSlib.h"
#include "fmv/console.h"
#include "fmv/psg.h"
#include "fmv/vdp.h"

#define FMV_SCREEN_BLANK_WORD   0x0000u
#define FMV_SCREEN_SPRITE_WORD  ((u16)((FMV_SCREEN_SPRITE_OFF << 8) | FMV_SCREEN_SPRITE_OFF))

void fmv_screen_reset(void)
{
    static_assert(FMV_SCREEN_NAME_TABLE + FMV_SCREEN_NAME_TABLE_BYTES == FMV_SCREEN_SAT,
                  "the name table ends where the sprite table starts");
    static_assert((FMV_SCREEN_IDLE_CELL & 0x01FFu) < FMV_SCREEN_RESERVED,
                  "the idle cell points inside the reserved patterns");
    static_assert(FMV_SCREEN_BACK_TABLE + FMV_SCREEN_NAME_TABLE_BYTES <= FMV_SCREEN_NAME_TABLE,
                  "the back table ends before the front one");
    static_assert(FMV_SCREEN_VRAM_BYTES % 2u == 0u && FMV_SCREEN_VRAM_BYTES > 0u,
                  "VRAM clears in whole words");
    static_assert(FMV_SCREEN_NAME_TABLE_BYTES % 2u == 0u && FMV_SCREEN_SPRITES % 2u == 0u,
                  "the tables fill in whole words");

    fmv_vdp_display_off();
    fmv_vdp_fill_words(0x0000u, FMV_SCREEN_BLANK_WORD, FMV_SCREEN_VRAM_BYTES / 2u);
    fmv_vdp_fill_words(FMV_SCREEN_NAME_TABLE, FMV_SCREEN_IDLE_CELL, FMV_SCREEN_NAME_TABLE_BYTES / 2u);
    fmv_vdp_fill_words(FMV_SCREEN_BACK_TABLE, FMV_SCREEN_IDLE_CELL, FMV_SCREEN_NAME_TABLE_BYTES / 2u);
    fmv_screen_table(FMV_SCREEN_FRONT_REGISTER);
    fmv_vdp_fill_words(FMV_SCREEN_SAT, FMV_SCREEN_SPRITE_WORD, FMV_SCREEN_SPRITES / 2u);
    fmv_set_bg_colour(0u, FMV_COLOUR_BLACK);
    fmv_set_sprite_colour(0u, FMV_COLOUR_BLACK);
    fmv_vdp_display_on();
}

void fmv_screen_fault(void)
{
    SMS_waitForVBlank();
    fmv_set_sprite_colour(0u, FMV_COLOUR_RED);
}

void fmv_screen_rest(void)
{
    fmv_psg_silence();
    fmv_screen_reset();
}
