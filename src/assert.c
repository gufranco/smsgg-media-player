#include "fmv/assert.h"

#include "SMSlib.h"
#include "fmv/console.h"
#include "fmv/vdp.h"

_Noreturn void fmv_assert_fail(u16 line)
{
    const fmv_colour colour = (fmv_colour)((line & 0x03u) | FMV_COLOUR_ASSERT);

    fmv_vdp_display_off();
    for (;;) {
        fmv_set_sprite_colour(0u, colour);
        SMS_waitForVBlank();
    }
}
