#include "fmv/osd.h"

#include "fmv/assert.h"
#include "fmv/budget.h"
#include "fmv/console.h"
#include "fmv/glyph.h"
#include "fmv/menuart.h"
#include "fmv/vdpcopy.h"

#define OSD_COLUMNS        8u
#define OSD_ROWS           5u
#define OSD_ROW_TOP        0u
#define OSD_ROW_BAR        1u
#define OSD_ROW_TEXT       3u
#define OSD_TEXT_FIRST     176u
#define OSD_ART_FIRST      (OSD_TEXT_FIRST + OSD_COLUMNS)
#define OSD_TILE_BLANK     244u
#define OSD_CELLS          (OSD_COLUMNS * 2u)
#define OSD_SPRITE_PIXELS  8u
#define OSD_X              96u
#define OSD_Y              127u
#define OSD_SAT_Y          0x3F00u
#define OSD_SAT_XN         0x3F80u
#define OSD_MENU_ENTRY     28u
#define OSD_MENU_COLOURS   4u
#define OSD_BAR_SPAN       (OSD_COLUMNS - 1u)
#define OSD_CLOCK_HZ       3579545ul
#define OSD_FIELD_CYCLES   (262ul * 228ul)
#define OSD_MILLI          1000ul
#define OSD_FIELD_HZ_MILLI ((OSD_CLOCK_HZ * OSD_MILLI + OSD_FIELD_CYCLES / 2ul) / OSD_FIELD_CYCLES)
#define OSD_SECONDS        60u
#define OSD_MAX_FIELDS     ((0xFFFFFFFFul - OSD_FIELD_HZ_MILLI) / OSD_MILLI)
#define OSD_WIDE_SECONDS   600u
#define OSD_MAX_SECONDS    (99u * OSD_SECONDS + OSD_SECONDS - 1u)
#define OSD_NARROW_SECONDS (9u * OSD_SECONDS + OSD_SECONDS - 1u)
#define OSD_INK_LINES      10u
#define OSD_ART_LINES      38u
#define OSD_CLOCK_LINES    98u
#define OSD_TEXT_LINES     49u
#define OSD_PLACE_LINES    96u

typedef enum {
    OSD_STEP_INKS = 0,
    OSD_STEP_ART = 1,
    OSD_STEP_TOTAL = OSD_STEP_ART + FMV_MENU_ART_TILES,
    OSD_STEP_ELAPSED = OSD_STEP_TOTAL + 1,
    OSD_STEP_TEXT = OSD_STEP_ELAPSED + 1,
    OSD_STEP_BLANK = OSD_STEP_TEXT + OSD_COLUMNS,
    OSD_STEP_PLACE = OSD_STEP_BLANK + 1,
    OSD_STEP_DONE = OSD_STEP_PLACE + 1
} osd_step;

static const u8 osd_lines[OSD_STEP_DONE] = {
    OSD_INK_LINES,   OSD_ART_LINES,   OSD_ART_LINES,   OSD_ART_LINES,  OSD_ART_LINES,
    OSD_ART_LINES,   OSD_ART_LINES,   OSD_ART_LINES,   OSD_CLOCK_LINES, OSD_CLOCK_LINES,
    OSD_TEXT_LINES,  OSD_TEXT_LINES,  OSD_TEXT_LINES,  OSD_TEXT_LINES, OSD_TEXT_LINES,
    OSD_TEXT_LINES,  OSD_TEXT_LINES,  OSD_TEXT_LINES,  OSD_ART_LINES,  OSD_PLACE_LINES,
};

static u8 osd_tile[FMV_GLYPH_TILE_BYTES];
static u8 osd_cells[OSD_CELLS];
static u16 osd_total;
static u8 osd_filled;
static u8 osd_next = OSD_STEP_DONE;
static bool osd_visible;

static u16 osd_seconds(u32 fields, u32 bias)
{
    u32 seconds;

    FMV_ASSERT(bias < OSD_FIELD_HZ_MILLI);
    FMV_ASSERT(fields <= OSD_MAX_FIELDS);
    seconds = (fields * OSD_MILLI + bias) / OSD_FIELD_HZ_MILLI;
    return (u16)(seconds > OSD_MAX_SECONDS ? OSD_MAX_SECONDS : seconds);
}

static u8 osd_put_clock(u8 at, u16 seconds)
{
    const bool wide = osd_total >= OSD_WIDE_SECONDS;
    const u16 shown = wide ? seconds : (seconds > OSD_NARROW_SECONDS ? OSD_NARROW_SECONDS : seconds);
    const u8 minutes = (u8)(shown / OSD_SECONDS);
    const u8 rest = (u8)(shown % OSD_SECONDS);

    FMV_ASSERT(at + (wide ? 5u : 4u) <= OSD_CELLS);
    FMV_ASSERT(shown <= OSD_MAX_SECONDS);
    if (wide) {
        osd_cells[at++] = (u8)(minutes / FMV_GLYPH_TENS);
    }
    osd_cells[at++] = (u8)(minutes % FMV_GLYPH_TENS);
    osd_cells[at++] = FMV_GLYPH_COLON;
    osd_cells[at++] = (u8)(rest / FMV_GLYPH_TENS);
    osd_cells[at++] = (u8)(rest % FMV_GLYPH_TENS);
    return at;
}

static u8 osd_clock_start(void)
{
    const u8 width = osd_total >= OSD_WIDE_SECONDS ? 5u : 4u;

    static_assert(5u * 2u + 1u <= OSD_CELLS, "the wide clock fits the text row");
    FMV_ASSERT(osd_total <= OSD_MAX_SECONDS);
    return (u8)(OSD_CELLS - (width * 2u + 1u));
}

static void osd_put_mute(u8 muted)
{
    const u8 at = osd_clock_start() > 6u ? 2u : 1u;
    static const u8 word[4] = {FMV_GLYPH_M, FMV_GLYPH_U, FMV_GLYPH_T, FMV_GLYPH_E};
    u8 index;

    FMV_ASSERT(at + 4u <= osd_clock_start());
    FMV_ASSERT(muted <= 1u);
    for (index = 0u; index < 4u; index++) {
        osd_cells[at + index] = muted != 0u ? word[index] : FMV_GLYPH_BLANK;
    }
}

static void osd_put_line(const fmv_osd_view *view)
{
    const u8 start = osd_clock_start();
    u8 at;

    FMV_ASSERT(view != 0);
    FMV_ASSERT(start < OSD_CELLS);
    for (at = 0u; at < start; at++) {
        osd_cells[at] = FMV_GLYPH_BLANK;
    }
    osd_cells[0] = view->paused != 0u ? FMV_GLYPH_PAUSE : FMV_GLYPH_PLAY;
    osd_put_mute(view->muted);
    at = osd_put_clock(start, osd_seconds(view->where.elapsed_fields, 0u));
    osd_cells[at] = FMV_GLYPH_SLASH;
    osd_put_clock((u8)(at + 1u), osd_total);
}

static u8 osd_fill(const fmv_position *where)
{
    FMV_ASSERT(where != 0);
    FMV_ASSERT(where->elapsed_fields <= OSD_MAX_FIELDS);
    static_assert(OSD_BAR_SPAN > 0u, "the bar has room for the knob to move");

    if (where->total_fields <= 1u) {
        return 0u;
    }
    if (where->elapsed_fields >= where->total_fields - 1u) {
        return OSD_BAR_SPAN;
    }
    return (u8)(where->elapsed_fields * OSD_BAR_SPAN / (where->total_fields - 1u));
}

static u8 osd_bar_art(u8 column)
{
    FMV_ASSERT(column < OSD_COLUMNS);
    FMV_ASSERT(osd_filled <= OSD_BAR_SPAN);

    if (column == osd_filled) {
        return FMV_MENU_ART_KNOB;
    }
    if (column < osd_filled) {
        return FMV_MENU_ART_FILLED;
    }
    if (column == 0u) {
        return FMV_MENU_ART_CAP_LEFT;
    }
    return column == OSD_BAR_SPAN ? FMV_MENU_ART_CAP_RIGHT : FMV_MENU_ART_EMPTY;
}

static u8 osd_sprite_tile(u8 sprite)
{
    const u8 row = (u8)(sprite / OSD_COLUMNS);
    const u8 column = (u8)(sprite % OSD_COLUMNS);

    FMV_ASSERT(sprite < FMV_OSD_SPRITES);
    FMV_ASSERT(row < OSD_ROWS);
    if (!osd_visible) {
        return OSD_TILE_BLANK;
    }
    switch (row) {
    case OSD_ROW_TOP:
        return (u8)(OSD_ART_FIRST + FMV_MENU_ART_TOP);
    case OSD_ROW_BAR:
        return (u8)(OSD_ART_FIRST + osd_bar_art(column));
    case OSD_ROW_TEXT:
        return (u8)(OSD_TEXT_FIRST + column);
    default:
        return (u8)(OSD_ART_FIRST + FMV_MENU_ART_PANEL);
    }
}

static void osd_place(void)
{
    u8 ys[FMV_OSD_SPRITES];
    u8 xn[FMV_OSD_SPRITES * 2u];
    u8 sprite;

    static_assert(FMV_OSD_SPRITES == OSD_COLUMNS * OSD_ROWS, "the panel is whole rows of sprites");
    for (sprite = 0u; sprite < FMV_OSD_SPRITES; sprite++) {
        ys[sprite] = (u8)(OSD_Y + (sprite / OSD_COLUMNS) * OSD_SPRITE_PIXELS);
        xn[sprite * 2u] = (u8)(OSD_X + (sprite % OSD_COLUMNS) * OSD_SPRITE_PIXELS);
        xn[sprite * 2u + 1u] = osd_sprite_tile(sprite);
    }
    fmv_vdp_write(OSD_SAT_XN, FMV_VDP_VRAM_WRITE, xn, (u8)sizeof xn);
    fmv_vdp_write(OSD_SAT_Y, FMV_VDP_VRAM_WRITE, ys, (u8)sizeof ys);
}

static void osd_upload_text(u8 column)
{
    FMV_ASSERT(column < OSD_COLUMNS);
    FMV_ASSERT(column * 2u + 1u < OSD_CELLS);

    fmv_glyph_text(osd_tile, osd_cells[column * 2u], osd_cells[column * 2u + 1u]);
    fmv_glyph_upload((u8)(OSD_TEXT_FIRST + column), osd_tile);
}

static void osd_upload_blank(void)
{
    static const u8 clear[FMV_GLYPH_TILE_BYTES] = {0u};

    fmv_glyph_upload(OSD_TILE_BLANK, clear);
}

static void osd_run(u8 step, const fmv_osd_view *view)
{
    FMV_ASSERT(step < OSD_STEP_DONE);
    FMV_ASSERT(view != 0);

    if (step == OSD_STEP_INKS) {
        fmv_osd_inks();
    } else if (step < OSD_STEP_TOTAL) {
        fmv_glyph_upload((u8)(OSD_ART_FIRST + step - OSD_STEP_ART), fmv_menu_art[step - OSD_STEP_ART]);
    } else if (step == OSD_STEP_TOTAL) {
        osd_total = osd_seconds(view->where.total_fields, OSD_FIELD_HZ_MILLI / 2u);
    } else if (step == OSD_STEP_ELAPSED) {
        osd_put_line(view);
        osd_filled = osd_fill(&view->where);
    } else if (step < OSD_STEP_BLANK) {
        osd_upload_text((u8)(step - OSD_STEP_TEXT));
    } else if (step == OSD_STEP_BLANK) {
        osd_upload_blank();
    } else {
        osd_place();
    }
}

static void osd_request(u8 step)
{
    if (step < osd_next) {
        osd_next = step;
    }
}

void fmv_osd_inks(void)
{
    static const fmv_colour inks[OSD_MENU_COLOURS] = {
        FMV_MENU_PANEL, FMV_MENU_INK, FMV_MENU_ACCENT, FMV_MENU_DIM,
    };

    fmv_vdp_write(OSD_MENU_ENTRY * FMV_CRAM_ENTRY_BYTES, FMV_VDP_CRAM_WRITE, (const u8 *)inks,
                  (u8)sizeof inks);
}

void fmv_osd_open(void)
{
    osd_visible = true;
    osd_next = OSD_STEP_INKS;
}

void fmv_osd_tick(void)
{
    if (osd_visible) {
        osd_request(OSD_STEP_ELAPSED);
    }
}

void fmv_osd_state(void)
{
    if (osd_visible) {
        osd_request(OSD_STEP_ELAPSED);
    }
}

void fmv_osd_close(void)
{
    osd_visible = false;
    osd_next = OSD_STEP_BLANK;
}

void fmv_osd_work(const fmv_osd_view *view)
{
    u8 count;
    u8 left = fmv_budget_lines();

    FMV_ASSERT(view != 0);
    FMV_ASSERT(osd_next <= OSD_STEP_DONE);
    for (count = 0u; count < OSD_STEP_DONE && osd_next < OSD_STEP_DONE; count++) {
        const u8 need = osd_lines[osd_next];
        u8 now;

        if (left < need) {
            return;
        }
        osd_run(osd_next, view);
        osd_next++;
        now = fmv_budget_lines();
        left = (u8)(left - need) < now ? (u8)(left - need) : now;
    }
}

void fmv_osd_show(const fmv_osd_view *view)
{
    u8 step;

    FMV_ASSERT(view != 0);
    FMV_ASSERT(view->where.elapsed_fields <= OSD_MAX_FIELDS);
    fmv_osd_open();
    for (step = OSD_STEP_INKS; step < OSD_STEP_DONE; step++) {
        osd_run(step, view);
    }
    osd_next = OSD_STEP_DONE;
}
