#ifndef FMV_VDP_H
#define FMV_VDP_H

#include "fmv/types.h"

#define FMV_VDP_MODE_REGISTER   1u
#define FMV_VDP_DISPLAY_OFF     0x20u
#define FMV_VDP_DISPLAY_ON      0x60u
#define FMV_VDP_FILL_VRAM_WRITE 0x40u

typedef struct {
    u8 low;
    u8 high;
    u8 first;
    u8 second;
    u16 words;
} fmv_vdp_span;

void fmv_vdp_register(u8 value, u8 reg);
void fmv_vdp_fill(const fmv_vdp_span *span);

static inline void fmv_vdp_fill_words(u16 address, u16 word, u16 words)
{
    const fmv_vdp_span span = {
        (u8)(address & 0xFFu),
        (u8)((address >> 8) | FMV_VDP_FILL_VRAM_WRITE),
        (u8)(word & 0xFFu),
        (u8)(word >> 8),
        words,
    };

    fmv_vdp_fill(&span);
}

static inline void fmv_vdp_display_on(void)
{
    fmv_vdp_register(FMV_VDP_DISPLAY_ON, FMV_VDP_MODE_REGISTER);
}

static inline void fmv_vdp_display_off(void)
{
    fmv_vdp_register(FMV_VDP_DISPLAY_OFF, FMV_VDP_MODE_REGISTER);
}

#endif
