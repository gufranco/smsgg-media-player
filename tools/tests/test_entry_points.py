from __future__ import annotations

import runpy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ENTRY_POINTS = (
    "tools/scripts/check_rom.py",
    "tools/scripts/check_vdp_timing.py",
    "tools/scripts/compare_capture.py",
    "tools/scripts/fetch_clips.py",
    "tools/scripts/make_demos.py",
    "tools/scripts/menu_art.py",
    "tools/scripts/render_psg.py",
    "tools/scripts/trace_vdp.py",
    "tools/smsggmedia/cartridge.py",
    "tools/smsggmedia/scout.py",
)


@pytest.mark.parametrize("entry", ENTRY_POINTS)
def test_running_the_file_reaches_its_command_line(entry, monkeypatch, capsys):
    # Arrange
    monkeypatch.setattr(sys, "argv", [entry, "--help"])

    # Act
    with pytest.raises(SystemExit) as exited:
        runpy.run_path(str(ROOT / entry), run_name="__main__")

    # Assert
    assert (exited.value.code, "usage:" in capsys.readouterr().out) == (0, True)
