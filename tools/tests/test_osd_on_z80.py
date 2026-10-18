from __future__ import annotations

import importlib.util
import struct
import sys
from pathlib import Path

import pytest
from z80vdp import (
    SAT_XN,
    SAT_Y,
    SPRITE_PATTERNS,
    TILE_BYTES,
    WHERE,
    Session,
    expected_pixels,
    load,
    pixels,
    run,
    sprites,
    tile,
)

from smsggmedia import console, lattice, menu

COLUMNS = 8
ROWS = 5
OSD_SPRITES = COLUMNS * ROWS
TEXT_FIRST = 176
TEXT_NUMBERS = list(range(TEXT_FIRST, TEXT_FIRST + COLUMNS))
ART_FIRST = TEXT_FIRST + COLUMNS
TOP, PANEL, CAP_LEFT, CAP_RIGHT, FILLED, EMPTY, KNOB = range(ART_FIRST, ART_FIRST + 7)
BLANK_TILE = 244
PANEL_X = 96
PANEL_Y = 127
BAR_ROW = slice(COLUMNS, 2 * COLUMNS)
GG_FIRST_LINE = 24
GG_LAST_LINE = 167
GG_FIRST_COLUMN = 48
GG_LAST_COLUMN = 207
MENU_ENTRIES = slice(28, 32)
FIELDS_PER_SECOND = console.NTSC_FIELD_HZ
FRAME_INTERRUPT_LINE = 0xC1
FIELD_LINES = 262
FIELD_LIMIT = 24
LATE_LINE = 190
BLANK_LINE = 200
PAUSED_AT = WHERE + 8
IDLE_CELLS = bytes([0x00, 0x08])
MENU_ART = Path(__file__).resolve().parents[1] / "scripts" / "menu_art.py"


@pytest.fixture(scope="module")
def built():
    return load()


@pytest.fixture(scope="module")
def art():
    spec = importlib.util.spec_from_file_location("menu_art", MENU_ART)
    if spec is None or spec.loader is None:
        msg = f"cannot import {MENU_ART}"
        raise AssertionError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules["menu_art"] = module
    spec.loader.exec_module(module)
    return module


def view(*, elapsed: int, total: int, paused: int = 0, muted: int = 0) -> bytes:
    return struct.pack("<IIBB", elapsed, total, paused, muted)


def fields(seconds: int) -> int:
    return round(seconds * FIELDS_PER_SECOND)


def shown(built, payload: bytes) -> Session:
    session = Session(built, payload)
    session.call("_fmv_osd_show")
    return session


def work_over_fields(session: Session) -> None:
    for _ in range(FIELD_LIMIT):
        session.vdp.start_at(0)
        session.call("_fmv_osd_work")


def request_and_draw(session: Session, request: str) -> None:
    session.call(request)
    work_over_fields(session)


def bar_tiles(vdp) -> list[int]:
    return [number for _, _, number in sprites(vdp)[BAR_ROW]]


def overlay_state(session: Session) -> tuple[bytes, ...]:
    vram = session.vdp.vram
    first = SPRITE_PATTERNS + TEXT_FIRST * TILE_BYTES
    last = SPRITE_PATTERNS + (BLANK_TILE + 1) * TILE_BYTES
    return (
        bytes(vram[first:last]),
        bytes(vram[SAT_Y : SAT_Y + OSD_SPRITES]),
        bytes(vram[SAT_XN : SAT_XN + 2 * OSD_SPRITES]),
        bytes(session.vdp.cram[MENU_ENTRIES]),
    )


class TestThePanel:
    def test_the_menu_colours_land_on_the_last_four_sprite_entries(self, built):
        # Arrange
        payload = view(elapsed=fields(1), total=fields(3))

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert list(vdp.cram[MENU_ENTRIES]) == menu.colours(lattice.MASTER_SYSTEM).tolist()

    def test_it_is_five_rows_of_eight_sprites(self, built):
        # Arrange
        payload = view(elapsed=fields(1), total=fields(3))

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert [(y, x) for y, x, _ in sprites(vdp)[:OSD_SPRITES]] == [
            (PANEL_Y + 8 * row, PANEL_X + 8 * column)
            for row in range(ROWS)
            for column in range(COLUMNS)
        ]

    def test_the_rows_are_edge_bar_panel_text_panel(self, built):
        # Arrange
        payload = view(elapsed=0, total=fields(3))

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        numbers = [number for _, _, number in sprites(vdp)[:OSD_SPRITES]]
        assert numbers[:COLUMNS] + numbers[2 * COLUMNS :] == (
            [TOP] * COLUMNS + [PANEL] * COLUMNS + TEXT_NUMBERS + [PANEL] * COLUMNS
        )

    def test_every_sprite_stays_inside_the_game_gear_window(self, built):
        # Arrange
        payload = view(elapsed=fields(1), total=fields(3))

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        placed = sprites(vdp)[:OSD_SPRITES]
        assert min(y + 1 for y, _, _ in placed) >= GG_FIRST_LINE
        assert max(y + 8 for y, _, _ in placed) <= GG_LAST_LINE + 1
        assert min(x for _, x, _ in placed) >= GG_FIRST_COLUMN
        assert max(x + 7 for _, x, _ in placed) <= GG_LAST_COLUMN

    def test_the_art_is_the_shared_menu_art(self, built, art):
        # Arrange
        payload = view(elapsed=0, total=fields(3))

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        uploaded = b"".join(tile(vdp, number) for number in range(TOP, KNOB + 1))
        assert uploaded == b"".join(art.tile_bytes(name) for _, name in art.TILES)


class TestTheBar:
    @pytest.mark.parametrize(
        ("elapsed", "expected"),
        [
            (0, [KNOB, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, EMPTY, CAP_RIGHT]),
            (90, [FILLED, FILLED, FILLED, KNOB, EMPTY, EMPTY, EMPTY, CAP_RIGHT]),
            (179, [FILLED] * 7 + [KNOB]),
        ],
        ids=["start", "half", "end"],
    )
    def test_the_knob_moves_along_the_bar_as_the_neo_geo_does(self, built, elapsed, expected):
        # Arrange
        payload = view(elapsed=elapsed, total=180)

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert bar_tiles(vdp) == expected

    def test_a_knob_past_the_first_cell_fills_the_cap_behind_it(self, built):
        # Arrange
        payload = view(elapsed=40, total=180)

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert bar_tiles(vdp)[:2] == [FILLED, KNOB]


class TestTheTextRow:
    def test_it_reads_icon_then_the_clock_on_the_right(self, built):
        # Arrange
        payload = view(elapsed=fields(65), total=fields(190))

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert pixels(vdp, TEXT_NUMBERS) == expected_pixels(">      1:05/3:10")

    def test_sound_off_writes_mute_after_the_icon(self, built):
        # Arrange
        payload = view(elapsed=fields(65), total=fields(190), muted=1)

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert pixels(vdp, TEXT_NUMBERS) == expected_pixels("> MUTE 1:05/3:10")

    def test_paused_shows_the_pause_glyph(self, built):
        # Arrange
        payload = view(elapsed=fields(65), total=fields(190), paused=1)

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert pixels(vdp, TEXT_NUMBERS) == expected_pixels("=      1:05/3:10")

    def test_a_film_of_ten_minutes_or_more_shows_two_minute_digits(self, built):
        # Arrange
        payload = view(elapsed=fields(65), total=fields(725), muted=1)

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert pixels(vdp, TEXT_NUMBERS) == expected_pixels(">MUTE01:05/12:05")

    def test_the_total_rounds_to_the_nearest_second(self, built):
        # Arrange
        payload = view(elapsed=0, total=fields(3) - 20)

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert pixels(vdp, TEXT_NUMBERS) == expected_pixels(">      0:00/0:03")

    def test_a_clock_past_99_minutes_holds_at_99_59(self, built):
        # Arrange
        payload = view(elapsed=fields(7000), total=fields(7200))

        # Act
        vdp = run(built, "_fmv_osd_show", payload)

        # Assert
        assert pixels(vdp, TEXT_NUMBERS) == expected_pixels(">    99:59/99:59")


class TestStateAndTick:
    def test_a_state_change_redraws_the_text(self, built):
        # Arrange
        session = shown(built, view(elapsed=0, total=fields(3)))
        session.poke(PAUSED_AT, bytes([1]))

        # Act
        request_and_draw(session, "_fmv_osd_state")

        # Assert
        assert pixels(session.vdp, TEXT_NUMBERS) == expected_pixels("=      0:00/0:03")

    def test_a_tick_redraws_the_elapsed_time(self, built):
        # Arrange
        session = shown(built, view(elapsed=fields(1), total=fields(10)))
        session.poke(WHERE, fields(5).to_bytes(4, "little"))

        # Act
        request_and_draw(session, "_fmv_osd_tick")

        # Assert
        assert pixels(session.vdp, TEXT_NUMBERS) == expected_pixels(">      0:05/0:10")

    def test_a_tick_moves_the_knob(self, built):
        # Arrange
        session = shown(built, view(elapsed=0, total=180))
        session.poke(WHERE, (90).to_bytes(4, "little"))

        # Act
        request_and_draw(session, "_fmv_osd_tick")

        # Assert
        assert bar_tiles(session.vdp)[3] == KNOB


class TestClose:
    def test_closing_points_every_panel_sprite_at_the_blank_tile(self, built):
        # Arrange
        session = shown(built, view(elapsed=0, total=180))

        # Act
        request_and_draw(session, "_fmv_osd_close")

        # Assert
        assert [number for _, _, number in sprites(session.vdp)[:OSD_SPRITES]] == (
            [BLANK_TILE] * OSD_SPRITES
        )

    def test_the_blank_tile_is_cleared_over_the_idle_name_table_cells(self, built):
        # Arrange
        session = Session(built, view(elapsed=fields(59), total=fields(61), muted=1))
        start = SPRITE_PATTERNS + BLANK_TILE * TILE_BYTES
        session.vdp.vram[start : start + TILE_BYTES] = IDLE_CELLS * (TILE_BYTES // 2)
        session.call("_fmv_osd_show")

        # Act
        request_and_draw(session, "_fmv_osd_close")

        # Assert
        assert tile(session.vdp, BLANK_TILE) == bytes(TILE_BYTES)

    def test_a_tick_while_closed_draws_nothing(self, built):
        # Arrange
        session = shown(built, view(elapsed=0, total=180))
        request_and_draw(session, "_fmv_osd_close")
        before = session.vdp.writes

        # Act
        request_and_draw(session, "_fmv_osd_tick")

        # Assert
        assert session.vdp.writes == before


class TestTheFieldBudget:
    @pytest.mark.parametrize("line", [*range(0, 192, 13), 191])
    def test_work_started_in_the_display_returns_before_the_frame_interrupt(self, built, line):
        # Arrange
        session = Session(built, view(elapsed=fields(3599), total=fields(7199), muted=1))
        session.call("_fmv_osd_open")
        session.vdp.start_at(line)

        # Act
        session.call("_fmv_osd_work")

        # Assert
        assert session.vdp.now() < FRAME_INTERRUPT_LINE

    def test_work_with_no_room_writes_nothing(self, built):
        # Arrange
        session = Session(built, view(elapsed=0, total=180))
        session.call("_fmv_osd_open")
        session.vdp.start_at(LATE_LINE)

        # Act
        session.call("_fmv_osd_work")

        # Assert
        assert session.vdp.writes == 0

    def test_work_in_the_vertical_blank_returns_before_the_next_one(self, built):
        # Arrange
        session = Session(built, view(elapsed=0, total=180))
        session.call("_fmv_osd_open")
        session.vdp.start_at(BLANK_LINE)

        # Act
        session.call("_fmv_osd_work")

        # Assert
        assert session.vdp.now() < FIELD_LINES + FRAME_INTERRUPT_LINE

    def test_work_spread_over_fields_draws_what_show_draws(self, built):
        # Arrange
        payload = view(elapsed=fields(61), total=fields(125), muted=1)
        session = Session(built, payload)
        session.call("_fmv_osd_open")

        # Act
        work_over_fields(session)

        # Assert
        assert overlay_state(session) == overlay_state(shown(built, payload))
