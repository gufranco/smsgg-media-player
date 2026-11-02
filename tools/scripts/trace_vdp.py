from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from smsggmedia import console, target

LUA: Final = Path(__file__).resolve().with_name("vdp_trace.lua")
DRIVERS: Final = {target.MASTER_SYSTEM.name: "sg1000m3", target.GAME_GEAR.name: "gamegear"}
DATA_PORT: Final = 0xBE
CONTROL_PORT: Final = 0xBF
COUNTER_PORT: Final = 0x7E
ACTIVE_LINES: Final = 192
ACTIVE_FLOOR: Final = 29
BLANK_FLOOR: Final = 16
REGISTER_CODE: Final = 2
CRAM_CODE: Final = 3
MODE_REGISTER: Final = 1
TABLE_REGISTER: Final = 2
DISPLAY_BIT: Final = 0x40
ATTO: Final = 10**18
DEFAULT_FRAMES: Final = 600
SECONDS_PER_FRAME: Final = 0.05
STARTUP_SECONDS: Final = 60.0
SHOWN: Final = 6
SPACING: Final = "port spacing"
BLANK_ONLY: Final = "palette or table flip outside the vertical blank"
LATCH: Final = "control latch"
COUNTER: Final = "counter port write"


@dataclass(frozen=True, slots=True)
class Record:
    frame: int
    port: int
    value: int
    scan: int
    pc: int
    time: float


@dataclass(frozen=True, slots=True)
class Finding:
    frame: int
    scan: int
    pc: int
    detail: str


Findings = dict[str, list[Finding]]


def parse(lines: Iterable[str]) -> list[Record]:
    return [
        _record([int(part) for part in fields])
        for fields in (text.split() for text in lines)
        if fields
    ]


def _record(values: list[int]) -> Record:
    frame, port, value, scan, pc, seconds, atto = values
    return Record(frame, port, value, scan, pc, seconds + atto / ATTO)


@dataclass(frozen=True, slots=True)
class _State:
    showing: bool = True
    latch: int | None = None
    code: int = 0
    previous: Record | None = None


def check(records: Sequence[Record], *, clock: int, first_frame: int = 0) -> Findings:
    found: Findings = {}
    state = _State()
    for record in records:
        problems, state = _step(record, state, clock)
        if record.frame >= first_frame:
            for name, detail in problems:
                found = {**found, name: [*found.get(name, []), _at(record, detail)]}
    return found


def _at(record: Record, detail: str) -> Finding:
    return Finding(record.frame, record.scan, record.pc, detail)


def _step(record: Record, state: _State, clock: int) -> tuple[list[tuple[str, str]], _State]:
    drawing = state.showing and record.scan < ACTIVE_LINES
    problems = _spacing(record, state.previous, drawing, clock)
    if record.port == COUNTER_PORT:
        return [*problems, (COUNTER, f"wrote {record.value:#04x} to the PSG through $7E")], state
    if record.port == DATA_PORT:
        latch = (
            [(LATCH, "data written between the two control bytes")]
            if state.latch is not None
            else []
        )
        palette = [(BLANK_ONLY, "palette byte")] if state.code == CRAM_CODE and drawing else []
        return [*problems, *latch, *palette], _State(state.showing, None, state.code, record)
    if state.latch is None:
        return problems, _State(state.showing, record.value, state.code, record)
    return _commit(record, state, problems, drawing)


def _commit(
    record: Record, state: _State, problems: list[tuple[str, str]], drawing: bool
) -> tuple[list[tuple[str, str]], _State]:
    code = record.value >> 6
    register = record.value & 0x0F
    low = state.latch if state.latch is not None else 0
    flip = code == REGISTER_CODE and register == TABLE_REGISTER and drawing
    showing = (
        bool(low & DISPLAY_BIT)
        if code == REGISTER_CODE and register == MODE_REGISTER
        else state.showing
    )
    extra = [(BLANK_ONLY, "name table flip")] if flip else []
    return [*problems, *extra], _State(showing, None, code, record)


def _spacing(
    record: Record, previous: Record | None, drawing: bool, clock: int
) -> list[tuple[str, str]]:
    if (
        previous is None
        or previous.frame != record.frame
        or COUNTER_PORT in (record.port, previous.port)
    ):
        return []
    gap = round((record.time - previous.time) * clock)
    need = ACTIVE_FLOOR if drawing else BLANK_FLOOR
    return (
        []
        if gap >= need
        else [(SPACING, f"{gap} T-states after the previous access, needs {need}")]
    )


def report(records: Sequence[Record], found: Findings) -> int:
    if not records:
        msg = "the trace holds nothing, so the run wrote nothing to the VDP"
        raise SystemExit(msg)
    frames = records[-1].frame - records[0].frame + 1
    print(f"{len(records)} port writes over {frames} frames")
    for name in sorted(found):
        items = found[name]
        routines = Counter(item.pc for item in items).most_common(SHOWN)
        print(
            f"  {name}: {len(items)}, by pc " + ", ".join(f"{pc:#06x} x{n}" for pc, n in routines)
        )
        for item in items[:SHOWN]:
            print(f"    frame {item.frame} line {item.scan} pc {item.pc:#06x}: {item.detail}")
    print("PASS" if not found else "FAIL")
    return 0 if not found else 1


def trace(
    rom: Path, *, frames: int, out: Path, system: str = target.MASTER_SYSTEM.name
) -> list[Record]:
    with tempfile.TemporaryDirectory() as work:
        script = Path(work) / "trace.lua"
        body = LUA.read_text().replace("CAPFRAMES", str(frames)).replace("CAPOUT", f'"{out}"')
        script.write_text(body)
        command = [
            "mame",
            DRIVERS[system],
            "-cart",
            str(rom.resolve()),
            "-window",
            "-video",
            "none",
            "-sound",
            "none",
            "-nothrottle",
            "-skip_gameinfo",
            "-script",
            str(script),
        ]
        environment = {**os.environ, "SDL_VIDEODRIVER": "dummy", "SDL_AUDIODRIVER": "dummy"}
        timeout = STARTUP_SECONDS + frames * SECONDS_PER_FRAME
        subprocess.run(
            command, cwd=work, env=environment, check=True, timeout=timeout, capture_output=True
        )
    return parse(out.read_text().splitlines())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Trace every VDP port write of a ROM under MAME and check the floors."
    )
    parser.add_argument("rom", type=Path)
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES)
    parser.add_argument("--out", type=Path, default=Path("build/vdp.trace"))
    parser.add_argument("--first-frame", type=int, default=0)
    parser.add_argument("--target", choices=sorted(DRIVERS), default=target.MASTER_SYSTEM.name)
    args = parser.parse_args(argv)
    records = trace(args.rom, frames=args.frames, out=args.out, system=args.target)
    found = check(records, clock=console.NTSC_CPU_HZ, first_frame=args.first_frame)
    return report(records, found)


if __name__ == "__main__":
    sys.exit(main())
