from __future__ import annotations

from itertools import pairwise

import pytest
from z80vdp import call, load, load_gg

SILENCE = [0x9F, 0xBF, 0xDF, 0xFF]
NAME_TABLE = 0x3800
IDLE_CELL = bytes([0x00, 0x08])
SPRITE_TABLE = 0x3F00
SPRITE_END = 0xD0
ROUTINE = "_fmv_screen_rest"
BACK_TABLE = 0x3000
TABLE_BYTES = 0x0700
SPRITES = 64
ACTIVE_FLOOR = 29
MODE_REGISTER = 1
DISPLAY_OFF = 0x20
DISPLAY_ON = 0x60
SPRITE_PALETTE = 16
GG_ENTRY_BYTES = 2


@pytest.fixture(scope="module", params=["sms", "gg"])
def console(request):
    built = load() if request.param == "sms" else load_gg()
    return built, request.param == "gg"


class TestPuttingTheConsoleAtRest:
    def test_every_psg_channel_is_attenuated_fully(self, console):
        # Arrange
        built, gg = console

        # Act
        vdp, _, _ = call(built, ROUTINE, gg=gg)

        # Assert
        assert vdp.sounds == SILENCE

    def test_the_name_table_draws_the_idle_cell(self, console):
        # Arrange
        built, gg = console

        # Act
        vdp, _, _ = call(built, ROUTINE, gg=gg)

        # Assert
        assert bytes(vdp.vram[NAME_TABLE : NAME_TABLE + 2]) == IDLE_CELL

    def test_every_sprite_is_parked_on_the_terminator(self, console):
        # Arrange
        built, gg = console

        # Act
        vdp, _, _ = call(built, ROUTINE, gg=gg)

        # Assert
        assert vdp.vram[SPRITE_TABLE] == SPRITE_END

    def test_every_vdp_access_keeps_the_active_display_floor(self, console):
        # Arrange
        built, gg = console

        # Act
        vdp, _, _ = call(built, ROUTINE, gg=gg)

        # Assert
        assert min(after - before for before, after in pairwise(vdp.stamps)) >= ACTIVE_FLOOR

    def test_the_display_goes_off_then_back_on(self, console):
        # Arrange
        built, gg = console

        # Act
        vdp, _, _ = call(built, ROUTINE, gg=gg)

        # Assert
        assert [value for register, value in vdp.registers if register == MODE_REGISTER] == [
            DISPLAY_OFF,
            DISPLAY_ON,
        ]

    def test_both_name_tables_hold_only_the_idle_cell(self, console):
        # Arrange
        built, gg = console

        # Act
        vdp, _, _ = call(built, ROUTINE, gg=gg)

        # Assert
        tables = [bytes(vdp.vram[base : base + TABLE_BYTES]) for base in (BACK_TABLE, NAME_TABLE)]
        assert tables == [IDLE_CELL * (TABLE_BYTES // len(IDLE_CELL))] * 2

    def test_the_whole_sprite_list_ends_at_the_first_slot(self, console):
        # Arrange
        built, gg = console

        # Act
        vdp, _, _ = call(built, ROUTINE, gg=gg)

        # Assert
        assert bytes(vdp.vram[SPRITE_TABLE : SPRITE_TABLE + SPRITES]) == bytes(
            [SPRITE_END] * SPRITES
        )

    def test_both_palettes_start_black(self, console):
        # Arrange
        built, gg = console
        width = GG_ENTRY_BYTES if gg else 1

        # Act
        vdp, _, _ = call(built, ROUTINE, gg=gg)

        # Assert
        entries = [0, SPRITE_PALETTE * width]
        assert vdp.cram_writes == [(base + i, 0) for base in entries for i in range(width)]
