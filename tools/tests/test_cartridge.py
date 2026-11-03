import argparse
import io
import json
import logging
import sys

import pytest
from fmvcore.testing import seeded
from lavfi import bake_only_argv, lavfi_clip

from smsggmedia import bake, cartridge, dials, limits, output

FAKE = seeded()
FILM = FAKE.file_name(extension="mp4")

pytestmark = pytest.mark.ffmpeg


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    return lavfi_clip(tmp_path_factory.mktemp("clip") / "source.mp4", size="320x240", rate=30)


class TestRoomPerFrame:
    def test_it_shares_the_cartridge_across_the_frames(self):
        # Arrange
        frame_count = 480

        # Act
        result = dials.room_per_frame(max_banks=62, frame_count=frame_count, fields=1)

        # Assert
        assert result == pytest.approx(62 * 16384 / 480)

    def test_padding_comes_out_of_the_share(self):
        # Arrange
        fields = 5

        # Act
        padded = dials.room_per_frame(max_banks=62, frame_count=480, fields=fields)

        # Assert
        assert padded == pytest.approx(62 * 16384 / 480 - 4)

    def test_a_longer_film_leaves_each_frame_less(self):
        # Arrange
        short = dials.room_per_frame(max_banks=62, frame_count=240, fields=5)

        # Act
        long = dials.room_per_frame(max_banks=62, frame_count=960, fields=5)

        # Assert
        assert long < short

    def test_it_never_returns_a_share_below_one_byte(self):
        # Arrange
        frame_count = 1_000_000

        # Act
        result = dials.room_per_frame(max_banks=1, frame_count=frame_count, fields=5)

        # Assert
        assert result >= 1.0

    def test_a_film_with_no_frames_is_refused(self):
        # Arrange
        frame_count = 0

        # Act
        with pytest.raises(ValueError) as refused:
            dials.room_per_frame(max_banks=62, frame_count=frame_count, fields=5)

        # Assert
        assert str(refused.value) == "a film needs at least one frame"


class TestGeometryFor:
    def test_the_picture_is_centred_in_the_visible_rows(self):
        # Arrange
        rows = 18

        # Act
        result = cartridge.geometry_for(32, rows)

        # Assert
        assert result.top_row == 3

    def test_a_full_height_picture_starts_at_the_top(self):
        # Arrange
        rows = 24

        # Act
        result = cartridge.geometry_for(32, rows)

        # Assert
        assert result.top_row == 0

    def test_the_geometry_carries_the_requested_shape(self):
        # Arrange
        rows = 18

        # Act
        result = cartridge.geometry_for(32, rows)

        # Assert
        assert (result.columns, result.rows) == (32, 18)


class TestWriteHeader:
    def test_it_states_the_bank_count(self, tmp_path):
        # Arrange
        target = tmp_path / "movie.h"

        # Act
        output.write_header(
            target,
            banks=7,
            frame_count=3,
            field_count=9,
            hold_fields=6,
            first_bank_symbol="movie_bin_PART0_bank",
        )

        # Assert
        assert "#define MOVIE_BANKS 7u" in target.read_text()

    def test_it_states_the_frame_count(self, tmp_path):
        # Arrange
        target = tmp_path / "movie.h"

        # Act
        output.write_header(
            target,
            banks=7,
            frame_count=3,
            field_count=9,
            hold_fields=6,
            first_bank_symbol="movie_bin_PART0_bank",
        )

        # Assert
        assert "#define MOVIE_FRAMES 3u" in target.read_text()

    def test_it_names_the_first_bank_symbol(self, tmp_path):
        # Arrange
        target = tmp_path / "movie.h"

        # Act
        output.write_header(
            target,
            banks=1,
            frame_count=1,
            field_count=9,
            hold_fields=6,
            first_bank_symbol="movie_bin_PART0_bank",
        )

        # Assert
        assert "#define MOVIE_FIRST_BANK movie_bin_PART0_bank" in target.read_text()

    def test_it_creates_the_directory(self, tmp_path):
        # Arrange
        target = tmp_path / "generated" / "movie.h"

        # Act
        output.write_header(
            target, banks=1, frame_count=1, field_count=9, hold_fields=6, first_bank_symbol="b"
        )

        # Assert
        assert target.is_file() is True


class TestMain:
    def test_it_writes_the_stream(self, clip, tmp_path):
        # Arrange
        argv = bake_only_argv(clip, tmp_path)

        # Act
        cartridge.main(argv)

        # Assert
        assert (tmp_path / "assets" / "movie.bin").stat().st_size > 0

    def test_the_stream_is_a_whole_number_of_banks(self, clip, tmp_path):
        # Arrange
        argv = bake_only_argv(clip, tmp_path)

        # Act
        cartridge.main(argv)

        # Assert
        size = (tmp_path / "assets" / "movie.bin").stat().st_size
        assert size % limits.BANK_BYTES == 0

    def test_it_writes_the_generated_header(self, clip, tmp_path):
        # Arrange
        argv = bake_only_argv(clip, tmp_path)

        # Act
        cartridge.main(argv)

        # Assert
        assert (tmp_path / "generated" / "movie.h").is_file() is True

    def test_the_report_counts_the_frames(self, clip, tmp_path):
        # Arrange
        argv = bake_only_argv(clip, tmp_path)

        # Act
        cartridge.main(argv)

        # Assert
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["frames"] > 0

    def test_the_report_names_the_dither_it_baked_with(self, clip, tmp_path):
        # Arrange
        argv = [*bake_only_argv(clip, tmp_path), "--dither", "0.5"]

        # Act
        cartridge.main(argv)

        # Assert
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["dither"] == 0.5

    def test_the_report_names_where_detail_was_merged_away(self, clip, tmp_path):
        # Arrange
        argv = bake_only_argv(clip, tmp_path)

        # Act
        cartridge.main(argv)

        # Assert
        report = json.loads((tmp_path / "report.json").read_text())
        named = report["most_merged_frames"]
        assert len(named) <= cartridge.MOST_MERGED_SHOWN
        assert all(0 <= frame < report["frames"] for frame in named)
        assert len(set(named)) == len(named)

    def test_a_preview_is_written_when_asked(self, clip, tmp_path):
        # Arrange
        path = tmp_path / "preview.png"

        # Act
        cartridge.main([*bake_only_argv(clip, tmp_path), "--preview", str(path)])

        # Assert
        assert path.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"

    def test_a_video_preview_is_written_when_the_name_asks_for_one(self, clip, tmp_path):
        # Arrange
        path = tmp_path / "preview.mp4"

        # Act
        cartridge.main([*bake_only_argv(clip, tmp_path), "--preview", str(path)])

        # Assert
        assert path.read_bytes()[4:8] == b"ftyp"

    def test_subtitles_are_announced_when_burned_in(self, clip, tmp_path, capsys):
        # Arrange
        cues = tmp_path / "cues.srt"
        cues.write_text("1\n00:00:00,000 --> 00:00:01,000\nHello\n\n")

        # Act
        cartridge.main([*bake_only_argv(clip, tmp_path), "--subtitles", str(cues)])

        # Assert
        assert "burning 1 subtitles into the picture" in capsys.readouterr().out

    def test_no_slot_collision_survives_a_bake(self, clip, tmp_path):
        # Arrange
        argv = bake_only_argv(clip, tmp_path)

        # Act
        cartridge.main(argv)

        # Assert
        report = json.loads((tmp_path / "report.json").read_text())
        assert report["slot_collisions"] == 0

    def test_a_clean_bake_reports_success(self, clip, tmp_path):
        # Arrange
        argv = bake_only_argv(clip, tmp_path)

        # Act
        result = cartridge.main(argv)

        # Assert
        assert result == 0


class TestBundle:
    def test_a_bundle_carries_the_film_the_cartridge_baked(self, clip, tmp_path):
        # Arrange
        argv = [*bake_only_argv(clip, tmp_path), "--bundle", str(tmp_path / "bundle")]

        # Act
        cartridge.main(argv)

        # Assert
        baked = (tmp_path / "assets" / "movie.bin").read_bytes()
        assert (tmp_path / "bundle" / "movie" / "assets" / "movie.bin").read_bytes() == baked

    def test_the_bundle_guide_names_the_picture_it_was_baked_for(self, clip, tmp_path):
        # Arrange
        argv = [*bake_only_argv(clip, tmp_path), "--bundle", str(tmp_path / "bundle")]

        # Act
        cartridge.main(argv)

        # Assert
        assert "a picture of 8 by 6 cells" in (tmp_path / "bundle" / "README.md").read_text()


UNCAPPED_FPS = 12.0


class TestDialReports:
    def test_reports_go_to_the_output_of_the_run_that_asked(self):
        # Arrange
        dials.LOG.addHandler(logging.StreamHandler(io.StringIO()))

        # Act
        cartridge.show_dial_reports()

        # Assert
        assert [handler.stream for handler in dials.LOG.handlers] == [sys.stdout]


def _tight(clip, tmp_path, *extra: str) -> list[str]:
    return [
        str(clip),
        "--duration",
        "1",
        "--max-banks",
        "1",
        "--denoise",
        "0",
        "--reuse",
        "0.008",
        "--assets",
        str(tmp_path / "assets"),
        "--generated",
        str(tmp_path / "generated"),
        "--report",
        str(tmp_path / "report.json"),
        "--bake-only",
        *extra,
    ]


class TestStepDown:
    def test_a_film_too_big_for_the_cartridge_steps_down_until_it_fits(self, clip, tmp_path):
        # Arrange
        argv = _tight(clip, tmp_path)

        # Act
        code = cartridge.main(argv)

        # Assert
        report = json.loads((tmp_path / "report.json").read_text())
        assert (code, report["banks"], report["fps"] < UNCAPPED_FPS) == (0, 1, True)

    def test_a_measured_reuse_never_buys_room_with_a_looser_threshold(self, clip, tmp_path):
        # Arrange
        argv = _tight(clip, tmp_path, "--reuse", "auto")

        # Act
        code = cartridge.main(argv)

        # Assert
        report = json.loads((tmp_path / "report.json").read_text())
        assert (code, report["banks"], report["reuse"] <= bake.DEFAULT_REUSE) == (0, 1, True)

    def test_a_film_no_rung_can_fit_is_refused_without_stepping_down(self, clip, tmp_path, capsys):
        # Arrange
        argv = [
            *_tight(clip, tmp_path),
            "--duration",
            "2",
            "--columns",
            "32",
            "--rows",
            "18",
            "--cap",
            "220",
            "--reuse",
            "0.0",
        ]

        # Act
        code = cartridge.main(argv)

        # Assert
        out = capsys.readouterr().out
        assert (code, "stepped down" in out, "not even one second" in out) == (2, False, True)

    def test_a_fixed_frame_rate_is_never_stepped_down(self, clip, tmp_path):
        # Arrange
        argv = _tight(clip, tmp_path, "--fps", "12")

        # Act
        code = cartridge.main(argv)

        # Assert
        report = json.loads((tmp_path / "report.json").read_text())
        assert (code, report["fps"]) == (2, 12.0)


def test_the_name_table_base_is_where_smslib_puts_it():
    # Arrange
    expected = 0x3800

    # Act
    base = bake.NAME_TABLE_BASE

    # Assert
    assert base == expected


class TestCapacity:
    def test_a_stream_inside_the_ceiling_fits(self):
        # Arrange
        banks = 40

        # Act
        result = cartridge.fits(banks=banks, max_banks=62)

        # Assert
        assert result is True

    def test_a_stream_over_the_ceiling_does_not(self):
        # Arrange
        banks = 200

        # Act
        result = cartridge.fits(banks=banks, max_banks=62)

        # Assert
        assert result is False

    def test_a_stream_exactly_at_the_ceiling_fits(self):
        # Arrange
        banks = 62

        # Act
        result = cartridge.fits(banks=banks, max_banks=62)

        # Assert
        assert result is True


def baked(*, collisions: int = 0, unshown_tail: int = 0) -> cartridge.Baked:
    return cartridge.Baked(
        encoded=bake.Encoded(collisions=collisions),
        fields=[],
        decoded=12,
        lags=[],
        lead=0,
        unshown_tail=unshown_tail,
        dither=limits.DEFAULT_DITHER,
        sources=[],
    )


class TestWhatABakeSays:
    def test_frames_the_clock_passed_at_the_end_are_named(self, capsys):
        # Arrange
        result = baked(unshown_tail=2)

        # Act
        cartridge._describe_bake(result, fps=12.0)

        # Assert
        assert "the clock passed the last 2 decoded frames" in capsys.readouterr().out

    def test_a_bake_with_a_slot_collision_writes_no_film(self, capsys):
        # Arrange
        args = argparse.Namespace(max_banks=limits.DEFAULT_MAX_BANKS)
        settled = dials.Dials(fps=12.0, denoise=0.0, reuse=0.008)

        # Act
        code = cartridge._refusal(args, baked=baked(collisions=3), banks=1, settled=settled)

        # Assert
        assert (code, "3 slot collisions" in capsys.readouterr().out) == (1, True)


class TestKeyFields:
    def test_a_seek_point_sits_on_the_field_its_frame_starts(self):
        # Arrange
        fields = [[b"a", b"b"], [b"c"], [b"d", b"e", b"f"]]

        # Act
        starts = cartridge.key_fields(fields, (0, 2))

        # Assert
        assert starts == [0, 3]
