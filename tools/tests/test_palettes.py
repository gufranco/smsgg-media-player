import dataclasses

import numpy as np
import pytest
from fmvcore.colour import blurred_error

from smsggmedia import lattice, palettes, pattern, smscolor
from smsggmedia import menu as menus


def fresh_fit(frame, **options):
    return palettes.fit_or_keep(frame, None, margin=0.0, **options)


def tiles_of(colours: list[int], count: int = 1) -> np.ndarray:
    out = np.zeros((len(colours) * count, pattern.TILE_PX, pattern.TILE_PX), dtype=np.uint8)
    for i, colour in enumerate(colours):
        out[i * count : (i + 1) * count] = colour
    return out


class TestChooseEntries:
    def test_it_returns_the_requested_number_of_entries(self):
        # Arrange
        present = np.arange(40, dtype=np.uint8)
        counts = np.ones(40, dtype=np.int64)

        # Act
        result = palettes.choose_entries(present, counts, lattice.MASTER_SYSTEM.oklab(), 16)

        # Assert
        assert result.shape == (16,)

    def test_no_colour_present_gives_a_palette_of_entry_zero(self):
        # Arrange
        present = np.array([], dtype=np.uint8)
        counts = np.array([], dtype=np.int64)

        # Act
        result = palettes.choose_entries(present, counts, lattice.MASTER_SYSTEM.oklab(), 4)

        # Assert
        assert result.tolist() == [0, 0, 0, 0]

    def test_colours_that_look_alike_still_fill_distinct_slots(self):
        # Arrange
        present = np.array([5, 9, 12], dtype=np.uint8)
        counts = np.array([10, 10, 10], dtype=np.int64)
        alike = np.zeros((64, 3), dtype=np.float32)

        # Act
        result = palettes.choose_entries(present, counts, alike, 2)

        # Assert
        assert result.tolist() == [5, 9]

    def test_fewer_present_colours_than_slots_are_all_kept(self):
        # Arrange
        present = np.array([0, 5, 63], dtype=np.uint8)
        counts = np.array([10, 10, 10], dtype=np.int64)

        # Act
        result = palettes.choose_entries(present, counts, lattice.MASTER_SYSTEM.oklab(), 16)

        # Assert
        assert set(result.tolist()) >= {0, 5, 63}

    def test_entries_are_unique(self):
        # Arrange
        present = np.arange(64, dtype=np.uint8)
        counts = np.ones(64, dtype=np.int64)

        # Act
        result = palettes.choose_entries(present, counts, lattice.MASTER_SYSTEM.oklab(), 16)

        # Assert
        assert len(set(result.tolist())) == 16

    def test_it_is_deterministic(self):
        # Arrange
        present = np.arange(64, dtype=np.uint8)
        counts = np.arange(1, 65, dtype=np.int64)
        lab = lattice.MASTER_SYSTEM.oklab()
        first = palettes.choose_entries(present, counts, lab, 16)

        # Act
        second = palettes.choose_entries(present, counts, lab, 16)

        # Assert
        assert first.tolist() == second.tolist()

    def test_asking_for_no_entries_is_refused(self):
        # Arrange
        present = np.array([0], dtype=np.uint8)
        counts = np.array([1], dtype=np.int64)
        lab = lattice.MASTER_SYSTEM.oklab()

        # Act
        with pytest.raises(ValueError) as refused:
            palettes.choose_entries(present, counts, lab, 0)

        # Assert
        assert str(refused.value) == "a palette needs at least one entry"


class TestFitFrame:
    def test_it_produces_two_palettes_of_sixteen(self):
        # Arrange
        rng = np.random.default_rng(7)
        frame = rng.integers(0, 256, size=(16, 32, 3), dtype=np.uint8)

        # Act
        result = fresh_fit(frame)

        # Assert
        assert result.cram.shape == (smscolor.CRAM_BYTES,)

    def test_every_cram_entry_is_a_console_colour(self):
        # Arrange
        rng = np.random.default_rng(8)
        frame = rng.integers(0, 256, size=(16, 32, 3), dtype=np.uint8)

        # Act
        result = fresh_fit(frame)

        # Assert
        assert int(result.cram.max()) < lattice.MASTER_SYSTEM.count

    def test_each_cell_picks_one_of_the_two_palettes(self):
        # Arrange
        rng = np.random.default_rng(9)
        frame = rng.integers(0, 256, size=(16, 32, 3), dtype=np.uint8)

        # Act
        result = fresh_fit(frame)

        # Assert
        assert set(np.unique(result.choice).tolist()) <= {0, 1}

    def test_indices_stay_inside_a_palette(self):
        # Arrange
        rng = np.random.default_rng(10)
        frame = rng.integers(0, 256, size=(16, 32, 3), dtype=np.uint8)

        # Act
        result = fresh_fit(frame)

        # Assert
        assert int(result.indices.max()) < smscolor.PALETTE_ENTRIES

    def test_a_flat_frame_reproduces_its_own_colour(self):
        # Arrange
        frame = np.full((16, 32, 3), 255, dtype=np.uint8)

        # Act
        result = fresh_fit(frame)

        # Assert
        assert result.render().min() == 255

    def test_a_two_colour_frame_survives_the_round_trip(self):
        # Arrange
        frame = np.zeros((16, 32, 3), dtype=np.uint8)
        frame[:, 16:] = 255

        # Act
        result = fresh_fit(frame)

        # Assert
        rendered = result.render()
        assert rendered[0, 0].tolist() == [0, 0, 0]
        assert rendered[0, 31].tolist() == [255, 255, 255]

    def test_the_cell_count_matches_the_frame_geometry(self):
        # Arrange
        frame = np.zeros((24, 32, 3), dtype=np.uint8)

        # Act
        result = fresh_fit(frame)

        # Assert
        assert result.choice.shape == (3 * 4,)

    def test_a_frame_without_a_colour_axis_is_refused(self):
        # Arrange
        frame = np.zeros((16, 32), dtype=np.uint8)

        # Act
        with pytest.raises(ValueError) as refused:
            fresh_fit(frame)

        # Assert
        assert str(refused.value) == "expected a trailing RGB axis, got shape (16, 32)"


class TestBackdropEntry:
    def test_the_border_entry_is_held_at_black(self):
        # Arrange
        frame = (np.arange(64 * 64 * 3, dtype=np.uint8) % 251).reshape(64, 64, 3)

        # Act
        fitted = fresh_fit(frame, chroma_weight=1.0)

        # Assert
        table = fitted.cram.reshape(smscolor.PALETTE_COUNT, smscolor.PALETTE_ENTRIES)
        assert table[1][palettes.BACKDROP_ENTRY] == palettes.BACKDROP_COLOUR

    def test_it_holds_on_a_bright_frame_too(self):
        # Arrange
        frame = np.full((64, 64, 3), 240, dtype=np.uint8)

        # Act
        fitted = fresh_fit(frame, chroma_weight=1.0)

        # Assert
        table = fitted.cram.reshape(smscolor.PALETTE_COUNT, smscolor.PALETTE_ENTRIES)
        assert table[1][palettes.BACKDROP_ENTRY] == palettes.BACKDROP_COLOUR

    def test_the_first_palette_is_left_alone(self):
        # Arrange
        frame = np.full((64, 64, 3), 240, dtype=np.uint8)

        # Act
        fitted = fresh_fit(frame, chroma_weight=1.0)

        # Assert
        table = fitted.cram.reshape(smscolor.PALETTE_COUNT, smscolor.PALETTE_ENTRIES)
        assert table[0][palettes.BACKDROP_ENTRY] != palettes.BACKDROP_COLOUR


class TestOrderedDither:
    def test_a_pale_gradient_takes_more_than_one_colour_per_cell(self):
        # Arrange
        frame = np.full((8, 8, 3), 128, dtype=np.uint8)

        # Act
        result = fresh_fit(frame, ordered_dither=1.0)

        # Assert
        assert np.unique(result.indices).size == 2

    def test_no_ordered_dither_keeps_a_flat_cell_flat(self):
        # Arrange
        frame = np.full((8, 8, 3), 128, dtype=np.uint8)

        # Act
        result = fresh_fit(frame, ordered_dither=0.0)

        # Assert
        assert np.unique(result.indices).size == 1


def more_colours_than_entries() -> np.ndarray:
    step = lattice.BYTE_MAX // lattice.GAME_GEAR.top
    colours = [
        (step * red, step * green, 0) for red in range(0, 16, 2) for green in range(0, 16, 3)
    ]
    cells = [np.full((8, 8, 3), colour, dtype=np.uint8) for colour in colours]
    return np.concatenate(cells, axis=1)


def cells_drawn_in_two_entries(fitted: palettes.FramePalettes) -> int:
    return sum(np.unique(cell).size == 2 for cell in fitted.indices)


class TestDitherAgainstThePalette:
    def test_a_game_gear_colour_left_out_of_the_palettes_is_mixed_from_two_entries(self):
        # Arrange
        frame = more_colours_than_entries()

        # Act
        fitted = fresh_fit(frame, ordered_dither=1.0, space=lattice.GAME_GEAR)

        # Assert
        assert cells_drawn_in_two_entries(fitted) > 0

    def test_without_dither_every_flat_cell_takes_its_nearest_entry(self):
        # Arrange
        frame = more_colours_than_entries()

        # Act
        fitted = fresh_fit(frame, ordered_dither=0.0, space=lattice.GAME_GEAR)

        # Assert
        assert cells_drawn_in_two_entries(fitted) == 0

    def test_a_colour_the_palette_holds_is_never_mixed(self):
        # Arrange
        frame = np.full((8, 8, 3), lattice.BYTE_MAX, dtype=np.uint8)

        # Act
        fitted = fresh_fit(frame, ordered_dither=1.0, space=lattice.GAME_GEAR)

        # Assert
        assert np.unique(fitted.indices).size == 1


NUDGE_SEED = 5
WHITE = (255, 255, 255)


def flat_frame(colour: tuple[int, int, int], noise_seed: int | None = None) -> np.ndarray:
    frame = np.zeros((16, 32, 3), dtype=np.uint8)
    frame[:] = colour
    frame[:, 16:] = (colour[2], colour[0], colour[1])
    if noise_seed is not None:
        rng = np.random.default_rng(noise_seed)
        frame = np.clip(frame.astype(np.int16) + rng.integers(-6, 7, frame.shape), 0, 255)
    return frame.astype(np.uint8)


def nudged_pair() -> tuple[palettes.FramePalettes, np.ndarray]:
    rng = np.random.default_rng(NUDGE_SEED)
    base = rng.integers(0, 256, (16, 16, 3), dtype=np.uint8)
    frame = base.copy()
    frame[:1, :8] = WHITE
    return fresh_fit(base), frame


class TestKeepingPalettes:
    def test_with_nothing_to_keep_the_frame_is_fitted_fresh(self):
        # Arrange
        frame = flat_frame((170, 85, 0))

        # Act
        result = palettes.fit_or_keep(frame, None, margin=0.3)

        # Assert
        assert result.render().tolist() == frame.tolist()

    def test_palettes_that_still_fit_are_kept_over_a_slightly_better_fit(self):
        # Arrange
        previous, frame = nudged_pair()

        # Act
        result = palettes.fit_or_keep(frame, previous.cram, margin=0.3)

        # Assert
        assert result.cram.tolist() == previous.cram.tolist()

    def test_with_no_margin_the_slightly_better_fit_wins(self):
        # Arrange
        previous, frame = nudged_pair()

        # Act
        result = palettes.fit_or_keep(frame, previous.cram, margin=0.0)

        # Assert
        assert result.cram.tolist() != previous.cram.tolist()

    def test_the_nudged_frame_really_fits_differently(self):
        # Arrange
        previous, frame = nudged_pair()

        # Act
        fresh = fresh_fit(frame)

        # Assert
        assert fresh.cram.tolist() != previous.cram.tolist()

    def test_palettes_from_a_different_picture_are_refitted(self):
        # Arrange
        previous = fresh_fit(flat_frame((170, 85, 0)))
        frame = flat_frame((0, 85, 255))

        # Act
        result = palettes.fit_or_keep(frame, previous.cram, margin=0.3)

        # Assert
        assert result.render().tolist() == frame.tolist()

    def test_a_negative_margin_is_refused(self):
        # Arrange
        frame = flat_frame((0, 0, 0))

        # Act
        with pytest.raises(ValueError) as raised:
            palettes.fit_or_keep(frame, None, margin=-0.1)

        # Assert
        assert str(raised.value) == "a palette keep margin must not be negative, got -0.1"


PAIRING_SEED = 11
BLOB_RADIUS = 0.01


def varied_frame(seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    frame = rng.integers(0, 256, (32, 64, 3), dtype=np.uint8)
    frame[:, 32:] = frame[:, 32:] // 2
    return frame


def second_palette_cost(table: np.ndarray, lab: np.ndarray, *, menu: bool = False) -> np.ndarray:
    last = menus.FILM_ENTRIES if menu else smscolor.PALETTE_ENTRIES
    first = lab[table[0][1:last]]
    second = lab[table[1][1:last]]
    return ((second[:, None, :] - first[None, :, :]) ** 2).sum(axis=-1)


def improving_swaps(cost: np.ndarray) -> int:
    size = cost.shape[0]
    return sum(
        cost[b, a] + cost[a, b] < cost[a, a] + cost[b, b]
        for a in range(size)
        for b in range(a + 1, size)
    )


class TestPairedPalettes:
    def test_no_swap_of_two_second_palette_entries_brings_it_closer_to_the_first(self):
        # Arrange
        frame = varied_frame(PAIRING_SEED)

        # Act
        fitted = fresh_fit(frame)

        # Assert
        table = fitted.cram.reshape(smscolor.PALETTE_COUNT, smscolor.PALETTE_ENTRIES)
        assert improving_swaps(second_palette_cost(table, lattice.MASTER_SYSTEM.oklab())) == 0

    def test_the_backdrop_and_the_menu_entries_never_move(self):
        # Arrange
        frame = varied_frame(PAIRING_SEED)

        # Act
        fitted = fresh_fit(frame, menu=True)

        # Assert
        table = fitted.cram.reshape(smscolor.PALETTE_COUNT, smscolor.PALETTE_ENTRIES)
        assert int(table[1][palettes.BACKDROP_ENTRY]) == palettes.BACKDROP_COLOUR
        expected = menus.colours(lattice.MASTER_SYSTEM).tolist()
        assert table[menus.MENU_PALETTE][menus.FILM_ENTRIES :].tolist() == expected

    def test_matching_undoes_a_reversed_order(self):
        # Arrange
        wanted = np.array([0.1, 0.5, 0.2, 0.9, 0.3])
        fresh = wanted[::-1]
        cost = (fresh[:, None] - wanted[None, :]) ** 2

        # Act
        order = palettes.matching(cost)

        # Assert
        assert fresh[order].tolist() == wanted.tolist()


def crowded_blob() -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    blob = np.random.default_rng(PAIRING_SEED).normal(0.0, 0.001, (60, 3))
    far = np.array(
        [[0.2 + 0.05 * step, 0.3 * (step % 3 - 1), 0.3 * (step % 2 * 2 - 1)] for step in range(15)]
    )
    points = np.concatenate([blob, far]).astype(np.float32)
    centres = np.concatenate([np.arange(11), 60 + np.arange(4)]).astype(np.intp)
    return points, np.ones(points.shape[0], dtype=np.float64), centres


WORSE_MIGRATION_SEED = 10
BLUR_CHOICE_SEED = 0


def game_gear_histogram(seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    present = np.unique(rng.integers(0, 4096, int(rng.integers(20, 80)))).astype(np.uint16)
    counts = rng.integers(1, 200, present.size).astype(np.float64)
    if rng.random() < 0.5:
        counts[: present.size // 3] *= 40
    return lattice.GAME_GEAR.oklab()[present], counts


class TestPaletteByBlur:
    def test_the_master_system_choice_draws_closer_to_the_source_once_blurred(self):
        # Arrange
        frame = np.random.default_rng(BLUR_CHOICE_SEED).integers(
            0, 256, (16, 16, 3), dtype=np.uint8
        )
        nearest = dataclasses.replace(lattice.MASTER_SYSTEM, palette_by_blur=False)
        by_nearest = fresh_fit(frame, ordered_dither=1.0, space=nearest)

        # Act
        by_blur = fresh_fit(frame, ordered_dither=1.0)

        # Assert
        assert by_blur.choice.tolist() != by_nearest.choice.tolist()
        blurred = blurred_error(by_blur.render()[None], frame[None])
        assert blurred < blurred_error(by_nearest.render()[None], frame[None])


class TestMigration:
    def test_centres_crowded_into_one_blob_move_out_one_a_round(self):
        # Arrange
        points, weight, centres = crowded_blob()

        # Act
        moved = palettes.migrated(points, weight, centres)

        # Assert
        in_blob = np.linalg.norm(points[moved], axis=1) < BLOB_RADIUS
        assert int(in_blob.sum()) == 11 - palettes.MIGRATION_ROUNDS

    def test_a_migration_that_would_raise_the_cost_is_discarded(self):
        # Arrange
        points, weight = game_gear_histogram(WORSE_MIGRATION_SEED)
        seeds = palettes._seed_centres(points, weight, count=16)
        centres = palettes._refine_centres(points, weight, seeds)

        # Act
        moved = palettes.migrated(points, weight, centres)

        # Assert
        assert moved.tolist() == centres.tolist()

    def test_a_single_entry_palette_is_left_alone(self):
        # Arrange
        present = np.array([3, 40, 2000], dtype=np.uint16)
        counts = np.array([5, 1, 1], dtype=np.int64)

        # Act
        result = palettes.choose_entries(
            present, counts, lattice.GAME_GEAR.oklab(), 1, migrate=True
        )

        # Assert
        assert result.tolist() == [3]


def grey_ramp() -> np.ndarray:
    ramp = np.linspace(0, 255, 64).astype(np.uint8)
    return np.repeat(np.repeat(ramp[None, :, None], 16, axis=0), 3, axis=2)


class TestTheGameGearLattice:
    def test_a_grey_ramp_keeps_more_greys_than_the_master_system_has(self):
        # Arrange
        frame = grey_ramp()

        # Act
        result = fresh_fit(frame, space=lattice.GAME_GEAR)

        # Assert
        greys = {tuple(pixel) for pixel in result.render().reshape(-1, 3).tolist()}
        assert len(greys) > lattice.MASTER_SYSTEM.levels

    def test_a_fitted_frame_names_the_lattice_it_was_fitted_on(self):
        # Arrange
        frame = grey_ramp()

        # Act
        result = fresh_fit(frame, space=lattice.GAME_GEAR)

        # Assert
        assert result.lattice is lattice.GAME_GEAR

    def test_its_render_is_closer_to_a_gradient_than_the_master_system_render(self):
        # Arrange
        frame = grey_ramp()
        narrow = np.abs(fresh_fit(frame).render().astype(int) - frame).mean()

        # Act
        result = fresh_fit(frame, space=lattice.GAME_GEAR)

        # Assert
        assert np.abs(result.render().astype(int) - frame).mean() < narrow
