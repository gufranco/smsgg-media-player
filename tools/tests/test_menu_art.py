from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "scripts" / "menu_art.py"
HEADER = ROOT / "include" / "fmv" / "menuart.h"


def load():
    spec = importlib.util.spec_from_file_location("menu_art", SCRIPT)
    if spec is None or spec.loader is None:
        msg = f"cannot import {SCRIPT}"
        raise AssertionError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules["menu_art"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def art():
    return load()


class TestThePlanarTile:
    def test_a_row_sets_each_plane_from_its_bit_of_the_index(self, art):
        # Arrange
        row = [13, 12, 0, 0, 0, 0, 0, 15]

        # Act
        planes = art.planar_row(row)

        # Assert
        assert planes == [0b10000001, 0b00000001, 0b11000001, 0b11000001]

    def test_a_tile_is_eight_rows_of_four_planes(self, art):
        # Arrange
        name = "panel"

        # Act
        tile = art.tile_bytes(name)

        # Assert
        assert tile == bytes([0x00, 0x00, 0xFF, 0xFF] * 8)


class TestTheCommittedHeader:
    def test_it_is_what_the_shared_art_generates(self, art):
        # Arrange
        expected = art.header()

        # Act
        committed = HEADER.read_text()

        # Assert
        assert committed == expected

    def test_writing_it_again_changes_nothing(self, art, tmp_path):
        # Arrange
        target = tmp_path / "menuart.h"

        # Act
        code = art.main(["--out", str(target)])

        # Assert
        assert (code, target.read_text()) == (0, HEADER.read_text())
