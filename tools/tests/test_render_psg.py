from __future__ import annotations

import importlib.util
import subprocess
import sys
import wave
from pathlib import Path

import pytest

from smsggmedia import psgplay, stream

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "scripts" / "render_psg.py"
FIELDS = 30
TONE = bytes([0x8E, 0x0F, 0x90])
RIGHT_ONLY = 0x0F


def load():
    spec = importlib.util.spec_from_file_location("render_psg", SCRIPT)
    if spec is None or spec.loader is None:
        msg = f"cannot import {SCRIPT}"
        raise AssertionError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules["render_psg"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def script():
    return load()


def movie(tmp_path: Path, *, pan: int | None = None) -> Path:
    first = (b"" if pan is None else stream.pan_run(pan)) + stream.psg_run(TONE)
    blob = first + bytes([stream.END_FRAME]) + bytes([stream.END_FRAME]) * (FIELDS - 1)
    path = tmp_path / "movie.bin"
    path.write_bytes(blob)
    return path


class TestRenderingABakedFilm:
    def test_a_master_system_film_renders_mono(self, script, tmp_path):
        # Arrange
        out = tmp_path / "film.wav"

        # Act
        script.main([str(movie(tmp_path)), "--out", str(out)])

        # Assert
        with wave.open(str(out)) as written:
            assert (written.getnchannels(), written.getframerate()) == (1, psgplay.SAMPLE_RATE)

    def test_a_game_gear_film_renders_both_sides(self, script, tmp_path):
        # Arrange
        out = tmp_path / "film.wav"

        # Act
        script.main([str(movie(tmp_path, pan=RIGHT_ONLY)), "--out", str(out), "--target", "gg"])

        # Assert
        with wave.open(str(out)) as written:
            assert written.getnchannels() == 2

    def test_the_audio_lasts_as_long_as_the_fields(self, script, tmp_path):
        # Arrange
        out = tmp_path / "film.wav"

        # Act
        script.main([str(movie(tmp_path)), "--out", str(out)])

        # Assert
        with wave.open(str(out)) as written:
            seconds = written.getnframes() / written.getframerate()
        assert seconds == pytest.approx(
            FIELDS * psgplay.TICKS_PER_FIELD / psgplay.TICK_HZ, abs=1e-3
        )

    def test_a_missing_film_is_refused_by_name(self, script, tmp_path):
        # Arrange
        missing = tmp_path / "nothing.bin"

        # Act
        with pytest.raises(SystemExit) as refused:
            script.main([str(missing), "--out", str(tmp_path / "film.wav")])

        # Assert
        assert str(missing) in str(refused.value)

    def test_the_script_runs_from_the_command_line(self, tmp_path):
        # Arrange
        out = tmp_path / "film.wav"
        command = [sys.executable, str(SCRIPT), str(movie(tmp_path)), "--out", str(out)]

        # Act
        done = subprocess.run(command, capture_output=True, text=True, check=False)

        # Assert
        assert (done.returncode, out.is_file()) == (0, True)
