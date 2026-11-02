from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "scripts" / "trace_vdp.py"
ROM = ROOT / "build" / "smsggmedia.sms"
GG_ROM = ROOT / "build" / "smsggmedia.gg"
MAME_REQUIRED_ENV = "SMSGGMEDIA_MAME_REQUIRED"
CLOCK = 3_579_545
DATA = 0xBE
CONTROL = 0xBF
COUNTER = 0x7E
BLANK_LINE = 200
ACTIVE_LINE = 100
TRACED_FRAMES = 120


def load():
    spec = importlib.util.spec_from_file_location("trace_vdp", SCRIPT)
    if spec is None or spec.loader is None:
        msg = f"cannot import {SCRIPT}"
        raise AssertionError(msg)
    module = importlib.util.module_from_spec(spec)
    sys.modules["trace_vdp"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tracer():
    return load()


def at(cycle: int) -> tuple[int, int]:
    seconds, rest = divmod(cycle, CLOCK)
    return seconds, rest * 10**18 // CLOCK


def line(port: int, value: int, *, cycle: int, scan: int, frame: int = 5, pc: int = 0x1234) -> str:
    seconds, atto = at(cycle)
    return f"{frame} {port} {value} {scan} {pc} {seconds} {atto}"


def display_on() -> list[str]:
    return [
        line(CONTROL, 0x60, cycle=0, scan=BLANK_LINE),
        line(CONTROL, 0x81, cycle=40, scan=BLANK_LINE),
    ]


def address(low: int, high: int, *, cycle: int, scan: int, gap: int = 30) -> list[str]:
    return [
        line(CONTROL, low, cycle=cycle, scan=scan),
        line(CONTROL, high, cycle=cycle + gap, scan=scan),
    ]


def findings(tracer, lines: list[str]):
    return tracer.check(tracer.parse(lines), clock=CLOCK)


class TestTheChecks:
    def test_a_vram_run_thirty_apart_in_active_display_is_clean(self, tracer):
        # Arrange
        lines = [
            *display_on(),
            *address(0x00, 0x40, cycle=1000, scan=ACTIVE_LINE),
            line(DATA, 1, cycle=1060, scan=ACTIVE_LINE),
            line(DATA, 2, cycle=1090, scan=ACTIVE_LINE),
        ]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert found == {}

    def test_data_twenty_eight_apart_in_active_display_is_found(self, tracer):
        # Arrange
        lines = [
            *display_on(),
            *address(0x00, 0x40, cycle=1000, scan=ACTIVE_LINE),
            line(DATA, 1, cycle=1060, scan=ACTIVE_LINE),
            line(DATA, 2, cycle=1088, scan=ACTIVE_LINE),
        ]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert list(found) == ["port spacing"]

    def test_sixteen_apart_in_the_vertical_blank_is_clean(self, tracer):
        # Arrange
        lines = [
            *display_on(),
            *address(0x00, 0xC0, cycle=1000, scan=BLANK_LINE),
            line(DATA, 1, cycle=1060, scan=BLANK_LINE),
            line(DATA, 2, cycle=1076, scan=BLANK_LINE),
        ]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert found == {}

    def test_an_address_pair_twelve_apart_is_found(self, tracer):
        # Arrange
        lines = [*display_on(), *address(0x00, 0x40, cycle=1000, scan=BLANK_LINE, gap=12)]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert list(found) == ["port spacing"]

    def test_a_palette_write_in_active_display_is_found(self, tracer):
        # Arrange
        lines = [
            *display_on(),
            *address(0x00, 0xC0, cycle=1000, scan=ACTIVE_LINE),
            line(DATA, 1, cycle=1060, scan=ACTIVE_LINE),
        ]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert list(found) == ["palette or table flip outside the vertical blank"]

    def test_a_table_flip_in_active_display_is_found(self, tracer):
        # Arrange
        lines = [*display_on(), *address(0xFD, 0x82, cycle=1000, scan=ACTIVE_LINE)]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert list(found) == ["palette or table flip outside the vertical blank"]

    def test_anything_goes_at_the_blanking_floor_with_the_display_off(self, tracer):
        # Arrange
        lines = [
            *address(0x20, 0x81, cycle=0, scan=ACTIVE_LINE),
            *address(0x00, 0xC0, cycle=1000, scan=ACTIVE_LINE),
            line(DATA, 1, cycle=1060, scan=ACTIVE_LINE),
            line(DATA, 2, cycle=1076, scan=ACTIVE_LINE),
        ]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert found == {}

    def test_a_data_write_between_the_two_control_bytes_is_found(self, tracer):
        # Arrange
        lines = [
            *display_on(),
            line(CONTROL, 0x00, cycle=1000, scan=BLANK_LINE),
            line(DATA, 1, cycle=1040, scan=BLANK_LINE),
        ]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert list(found) == ["control latch"]

    def test_a_write_to_the_counter_port_is_found(self, tracer):
        # Arrange
        lines = [*display_on(), line(COUNTER, 0x9F, cycle=1000, scan=BLANK_LINE)]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert list(found) == ["counter port write"]

    def test_gaps_across_frames_are_not_compared(self, tracer):
        # Arrange
        lines = [
            *display_on(),
            *address(0x00, 0x40, cycle=1000, scan=BLANK_LINE),
            line(DATA, 1, cycle=1060, scan=BLANK_LINE),
            line(DATA, 2, cycle=1062, scan=BLANK_LINE, frame=6),
        ]

        # Act
        found = findings(tracer, lines)

        # Assert
        assert found == {}

    def test_findings_before_the_first_frame_asked_for_are_left_out(self, tracer):
        # Arrange
        lines = [*display_on(), line(COUNTER, 0x9F, cycle=1000, scan=BLANK_LINE, frame=3)]

        # Act
        found = tracer.check(tracer.parse(lines), clock=CLOCK, first_frame=4)

        # Assert
        assert found == {}


class TestTheReport:
    def test_a_clean_trace_passes(self, tracer, capsys):
        # Arrange
        records = tracer.parse(display_on())

        # Act
        code = tracer.report(records, {})

        # Assert
        assert (code, "PASS" in capsys.readouterr().out) == (0, True)

    def test_a_finding_fails_and_names_its_routine(self, tracer, capsys):
        # Arrange
        lines = [*display_on(), line(COUNTER, 0x9F, cycle=1000, scan=BLANK_LINE, pc=0xBEEF)]
        records = tracer.parse(lines)

        # Act
        code = tracer.report(records, tracer.check(records, clock=CLOCK))

        # Assert
        assert (code, "0xbeef" in capsys.readouterr().out) == (1, True)

    def test_an_empty_trace_fails_rather_than_passing(self, tracer):
        # Arrange
        records = tracer.parse([])

        # Act
        with pytest.raises(SystemExit) as refused:
            tracer.report(records, {})

        # Assert
        assert "nothing" in str(refused.value)


def mame_or_skip(rom: Path) -> None:
    reason = ""
    if shutil.which("mame") is None:
        reason = "mame is not on the path"
    elif not rom.is_file():
        reason = f"no ROM at {rom}; run make rom"
    if not reason:
        return
    if os.environ.get(MAME_REQUIRED_ENV) == "1":
        pytest.fail(reason)
    pytest.skip(reason)


class TestTheBuiltRoms:
    @pytest.mark.parametrize(("system", "rom"), [("sms", ROM), ("gg", GG_ROM)])
    def test_two_seconds_from_power_on_keep_every_rule(self, tracer, tmp_path, system, rom):
        # Arrange
        mame_or_skip(rom)
        trace = tmp_path / "rom.trace"

        # Act
        records = tracer.trace(rom, frames=TRACED_FRAMES, out=trace, system=system)

        # Assert
        assert (len(records) > 0, tracer.check(records, clock=CLOCK)) == (True, {})

    def test_the_command_line_passes_the_master_system_rom(self, tracer, tmp_path, capsys):
        # Arrange
        mame_or_skip(ROM)
        argv = [str(ROM), "--frames", str(TRACED_FRAMES), "--out", str(tmp_path / "cli.trace")]

        # Act
        code = tracer.main(argv)

        # Assert
        assert (code, "PASS" in capsys.readouterr().out) == (0, True)
