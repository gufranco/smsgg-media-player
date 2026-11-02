from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from smsggmedia import psgplay, stream

A440_LATCH = 0x8E
A440_DATA = 0x0F
A440_HZ = 3_579_545 / (32 * 0x0FE)
FULL_VOLUME_CHANNEL_0 = 0x90
STEP_DOWN_CHANNEL_0 = 0x91
WHITE_NOISE_FAST = 0xE4
FULL_VOLUME_NOISE = 0xF0
CONSTANT_LATCH = 0x81
CONSTANT_DATA = 0x00
RIGHT_ONLY = 0x0F
SECOND = 60
TWO_DB = 10 ** (-2 / 20)


def tone_fields(volume: int = FULL_VOLUME_CHANNEL_0, count: int = SECOND) -> list[psgplay.Field]:
    first = psgplay.Field(writes=bytes([A440_LATCH, A440_DATA, volume]), pan=None)
    return [first, *[psgplay.Field(writes=b"", pan=None)] * (count - 1)]


class TestTheChipRegisters:
    def test_a_latch_and_a_data_byte_set_a_ten_bit_period(self):
        # Arrange
        chip = psgplay.Chip()

        # Act
        written = chip.write_all(bytes([A440_LATCH, A440_DATA]))

        # Assert
        assert written.periods[0] == 0x0FE

    def test_a_noise_write_resets_the_shift_register(self):
        # Arrange
        chip = replace(psgplay.Chip(), lfsr=0x1234)

        # Act
        written = chip.write_all(bytes([WHITE_NOISE_FAST]))

        # Assert
        assert written.lfsr == psgplay.LFSR_RESET

    def test_every_channel_starts_silent(self):
        # Arrange
        chip = psgplay.Chip()

        # Act
        volumes = chip.volumes

        # Assert
        assert volumes == (psgplay.SILENT,) * psgplay.CHANNELS


class TestRendering:
    def test_register_0xfe_plays_a_440_hz_tone(self):
        # Arrange
        fields = tone_fields()

        # Act
        sound = psgplay.render(fields)

        # Assert
        spectrum = np.abs(np.fft.rfft(sound[:, 0]))
        peak = np.fft.rfftfreq(len(sound), 1 / psgplay.SAMPLE_RATE)[int(spectrum.argmax())]
        assert peak == pytest.approx(A440_HZ, abs=2.0)

    def test_a_chip_nobody_writes_stays_silent(self):
        # Arrange
        fields = [psgplay.Field(writes=b"", pan=None)] * SECOND

        # Act
        sound = psgplay.render(fields)

        # Assert
        assert not sound.any()

    def test_one_attenuation_step_is_two_decibels(self):
        # Arrange
        loud, quiet = tone_fields(), tone_fields(STEP_DOWN_CHANNEL_0)

        # Act
        ratio = np.abs(psgplay.render(quiet)).max() / np.abs(psgplay.render(loud)).max()

        # Assert
        assert ratio == pytest.approx(TWO_DB, rel=1e-3)

    def test_white_noise_sounds(self):
        # Arrange
        fields = [psgplay.Field(writes=bytes([WHITE_NOISE_FAST, FULL_VOLUME_NOISE]), pan=None)]

        # Act
        sound = psgplay.render(fields * SECOND)

        # Assert
        assert len(np.unique(sound[:, 0])) == 2

    def test_a_period_of_one_holds_the_output_high(self):
        # Arrange
        writes = bytes([CONSTANT_LATCH, CONSTANT_DATA, FULL_VOLUME_CHANNEL_0])
        fields = [psgplay.Field(writes=writes, pan=None)]

        # Act
        sound = psgplay.render(fields)

        # Assert
        assert len(np.unique(sound[:, 0])) == 1
        assert sound[0, 0] > 0

    def test_a_game_gear_pan_to_the_right_leaves_the_left_silent(self):
        # Arrange
        first = psgplay.Field(
            writes=bytes([A440_LATCH, A440_DATA, FULL_VOLUME_CHANNEL_0]), pan=RIGHT_ONLY
        )

        # Act
        sound = psgplay.render([first, *[psgplay.Field(writes=b"", pan=None)] * 9], stereo=True)

        # Assert
        assert not sound[:, 0].any()
        assert sound[:, 1].any()


class TestTheBakedStream:
    def test_each_field_keeps_its_own_writes(self):
        # Arrange
        blob = stream.psg_run(bytes([0x9F])) + bytes([stream.END_FRAME])
        blob += (
            stream.pan_run(RIGHT_ONLY)
            + stream.psg_run(bytes([0xBF, 0xDF]))
            + bytes([stream.END_FRAME])
        )

        # Act
        fields = psgplay.fields_of(blob)

        # Assert
        assert fields == [
            psgplay.Field(writes=bytes([0x9F]), pan=None),
            psgplay.Field(writes=bytes([0xBF, 0xDF]), pan=RIGHT_ONLY),
        ]
