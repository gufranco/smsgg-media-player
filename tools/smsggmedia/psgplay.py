from __future__ import annotations

import math
import wave
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Final

import numpy as np
import numpy.typing as npt

from smsggmedia import console, replay

DIVIDER: Final = 16
TICK_HZ: Final = console.NTSC_CPU_HZ / DIVIDER
TICKS_PER_FIELD: Final = console.NTSC_LINES * console.CYCLES_PER_LINE / DIVIDER
SAMPLE_RATE: Final = 44_100
CHANNELS: Final = 4
TONES: Final = 3
NOISE: Final = 3
SILENT: Final = 15
STEP_DB: Final = 2.0
LATCH: Final = 0x80
VOLUME_BIT: Final = 0x10
LOW_BITS: Final = 0x0F
HIGH_BITS: Final = 0x3F
NOISE_BITS: Final = 0x07
WHITE_BIT: Final = 0x04
RATE_BITS: Final = 0x03
FOLLOWS_TONE: Final = 3
NOISE_RELOADS: Final = (0x10, 0x20, 0x40)
LFSR_RESET: Final = 0x8000
LFSR_TAPS: Final = 0x0009
LFSR_TOP: Final = 15
STEADY_PERIOD: Final = 1
BOTH_SIDES: Final = 0xFF
LEFT_SHIFT: Final = 4
SAMPLE_BYTES: Final = 2
HEADROOM: Final = 0.8
FULL_SCALE: Final = 32767

Samples = npt.NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class Field:
    writes: bytes
    pan: int | None


@dataclass(frozen=True, slots=True)
class Chip:
    periods: tuple[int, ...] = (0,) * TONES
    volumes: tuple[int, ...] = (SILENT,) * CHANNELS
    noise: int = 0
    lfsr: int = LFSR_RESET
    latched: int = 0
    latched_volume: bool = True

    def write_all(self, data: bytes) -> Chip:
        chip = self
        for value in data:
            chip = chip.write(value)
        return chip

    def write(self, value: int) -> Chip:
        if value & LATCH:
            latched = replace(
                self, latched=(value >> 5) & RATE_BITS, latched_volume=bool(value & VOLUME_BIT)
            )
            return latched.store(value & LOW_BITS, low=True)
        return self.store(value & HIGH_BITS, low=False)

    def store(self, data: int, *, low: bool) -> Chip:
        channel = self.latched
        if self.latched_volume:
            return replace(self, volumes=_with(self.volumes, channel, data & LOW_BITS))
        if channel == NOISE:
            return replace(self, noise=data & NOISE_BITS, lfsr=LFSR_RESET)
        period = self.periods[channel]
        stored = (period & ~LOW_BITS) | data if low else (period & LOW_BITS) | (data << 4)
        return replace(self, periods=_with(self.periods, channel, stored))


@dataclass(frozen=True, slots=True)
class Voice:
    due: float = 0.0
    bit: int = 1
    out: int = 0


def _with(values: tuple[int, ...], index: int, value: int) -> tuple[int, ...]:
    return (*values[:index], value, *values[index + 1 :])


def fields_of(blob: bytes) -> list[Field]:
    machine = replay.Machine()
    fields: list[Field] = []
    for chunk in replay.frames_of(blob):
        sounds, pans = len(machine.psg), len(machine.pans)
        machine.apply(chunk)
        pan = machine.pans[-1] if len(machine.pans) > pans else None
        fields = [*fields, Field(writes=bytes(machine.psg[sounds:]), pan=pan)]
    return fields


def render(fields: list[Field], *, stereo: bool = False) -> Samples:
    chip, pan = Chip(), BOTH_SIDES
    voices: tuple[Voice, ...] = (Voice(),) * CHANNELS
    parts: list[Samples] = []
    for index, each in enumerate(fields):
        chip = chip.write_all(each.writes)
        pan = pan if each.pan is None else each.pan
        levels, voices, chip = _field(chip, voices, index)
        parts = [*parts, _mix(levels, chip.volumes, pan, stereo=stereo)]
    return np.concatenate(parts) if parts else np.zeros((0, 2 if stereo else 1))


def _field(
    chip: Chip, voices: tuple[Voice, ...], index: int
) -> tuple[list[Samples], tuple[Voice, ...], Chip]:
    start, end = index * TICKS_PER_FIELD, (index + 1) * TICKS_PER_FIELD
    first = math.ceil(start * SAMPLE_RATE / TICK_HZ)
    last = math.ceil(end * SAMPLE_RATE / TICK_HZ)
    times = np.arange(first, last, dtype=np.float64) * TICK_HZ / SAMPLE_RATE
    tones = [
        _tone(chip.periods[channel], voices[channel], times, (start, end))
        for channel in range(TONES)
    ]
    noise, voice, lfsr = _noise(chip, voices[NOISE], times, (start, end))
    levels = [level for level, _ in tones] + [noise]
    return levels, (*(state for _, state in tones), voice), replace(chip, lfsr=lfsr)


def _toggles(due: float, period: float, start: float, end: float) -> tuple[float, int]:
    first = max(due, start)
    return first, (math.ceil((end - first) / period) if first < end else 0)


def _tone(
    period: int, voice: Voice, times: Samples, span: tuple[float, float]
) -> tuple[Samples, Voice]:
    start, end = span
    if period <= STEADY_PERIOD:
        return np.ones_like(times), replace(voice, due=end, bit=1)
    first, count = _toggles(voice.due, period, start, end)
    flips = np.where(times >= first, np.floor((times - first) / period) + 1, 0)
    level = np.asarray((voice.bit + flips) % 2, dtype=np.float64)
    return level, replace(voice, due=first + count * period, bit=voice.bit ^ (count & 1))


def _noise(
    chip: Chip, voice: Voice, times: Samples, span: tuple[float, float]
) -> tuple[Samples, Voice, int]:
    start, end = span
    rate = chip.noise & RATE_BITS
    period = max(chip.periods[TONES - 1] if rate == FOLLOWS_TONE else NOISE_RELOADS[rate], 1)
    first, count = _toggles(voice.due, period, start, end)
    bit, lfsr = voice.bit, chip.lfsr
    shifts: list[float] = []
    outputs: list[int] = [voice.out]
    for step in range(count):
        bit ^= 1
        if bit:
            out, lfsr = _shift(lfsr, white=bool(chip.noise & WHITE_BIT))
            shifts, outputs = [*shifts, first + step * period], [*outputs, out]
    held = np.asarray(outputs, dtype=np.float64)[np.searchsorted(shifts, times, side="right")]
    return held, Voice(due=first + count * period, bit=bit, out=outputs[-1]), lfsr


def _shift(lfsr: int, *, white: bool) -> tuple[int, int]:
    out = lfsr & 1
    fed = bin(lfsr & LFSR_TAPS).count("1") & 1 if white else out
    return out, (lfsr >> 1) | (fed << LFSR_TOP)


def _gain(volume: int) -> float:
    return 0.0 if volume >= SILENT else float(10 ** (-STEP_DB * volume / 20))


def _mix(levels: list[Samples], volumes: tuple[int, ...], pan: int, *, stereo: bool) -> Samples:
    voices = np.stack(
        [(2.0 * level - 1.0) * _gain(volume) for level, volume in zip(levels, volumes, strict=True)]
    )
    if not stereo:
        return np.asarray(voices.sum(axis=0) / CHANNELS)[:, None]
    left = [(pan >> (LEFT_SHIFT + channel)) & 1 for channel in range(CHANNELS)]
    right = [(pan >> channel) & 1 for channel in range(CHANNELS)]
    return np.asarray((np.array([left, right], dtype=np.float64) @ voices).T / CHANNELS)


def write_wav(path: Path, sound: Samples) -> None:
    samples = np.clip(sound * HEADROOM * FULL_SCALE, -FULL_SCALE, FULL_SCALE).astype("<i2")
    with wave.open(str(path), "wb") as out:
        out.setnchannels(sound.shape[1])
        out.setsampwidth(SAMPLE_BYTES)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(samples.tobytes())
