from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pytest

from smsggmedia import lattice, menu, palettes


class TestTheMenuColours:
    def test_the_master_system_entries_are_the_nearest_of_its_64(self):
        # Arrange
        space = lattice.MASTER_SYSTEM

        # Act
        entries = menu.colours(space).tolist()

        # Assert
        assert entries == [0x00, 0x3F, 0x0B, 0x15]

    def test_the_game_gear_entries_are_the_nearest_of_its_4096(self):
        # Arrange
        space = lattice.GAME_GEAR

        # Act
        entries = menu.colours(space).tolist()

        # Assert
        assert entries == [0x0100, 0x0FFF, 0x019F, 0x0766]

    def test_the_menu_takes_the_last_four_sprite_palette_entries(self):
        # Arrange
        expected = (12, 13, 14, 15)

        # Act
        entries = menu.ENTRIES

        # Assert
        assert entries == expected


class TestTheArtIndices:
    def test_each_art_code_draws_in_its_reserved_entry(self):
        # Arrange
        codes = (".", "#", "*", "-", "=", " ")

        # Act
        indices = [menu.INDEX_OF[code] for code in codes]

        # Assert
        assert indices == [12, 13, 14, 15, 15, 0]


class TestAFittedPalette:
    @pytest.mark.parametrize("space", [lattice.MASTER_SYSTEM, lattice.GAME_GEAR], ids=["sms", "gg"])
    def test_its_last_four_sprite_entries_are_the_menu(self, space):
        # Arrange
        rng = np.random.default_rng(3)
        frame = rng.integers(0, 256, size=(16, 16, 3), dtype=np.uint8)

        # Act
        fitted = palettes.fit_or_keep(frame, None, margin=0.3, space=space, menu=True)

        # Assert
        assert fitted.cram[28:32].tolist() == menu.colours(space).tolist()

    def test_without_the_menu_the_film_keeps_all_sixteen_sprite_entries(self):
        # Arrange
        rng = np.random.default_rng(3)
        frame = rng.integers(0, 256, size=(16, 16, 3), dtype=np.uint8)

        # Act
        fitted = palettes.fit_or_keep(frame, None, margin=0.3)

        # Assert
        assert len(set(fitted.cram[16:32].tolist())) == 16


ROOT = Path(__file__).resolve().parents[2]
NAMES = ("PANEL", "INK", "ACCENT", "DIM")


def player_colours(system: str) -> list[int]:
    text = (ROOT / "src" / system / "fmv_target.h").read_text()
    return [
        int(re.search(rf"^#define FMV_MENU_{name}\s+(0x[0-9A-Fa-f]+)u$", text, re.MULTILINE)[1], 16)
        for name in NAMES
    ]


class TestThePlayerAgrees:
    @pytest.mark.parametrize(
        ("system", "space"),
        [("sms", lattice.MASTER_SYSTEM), ("gg", lattice.GAME_GEAR)],
        ids=["sms", "gg"],
    )
    def test_its_menu_colours_are_the_ones_the_baker_reserves(self, system, space):
        # Arrange
        reserved = menu.colours(space).tolist()

        # Act
        written = player_colours(system)

        # Assert
        assert written == reserved
