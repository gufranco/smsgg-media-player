from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fmvcore import font

from smsggmedia import menu

ROOT: Final = Path(__file__).resolve().parents[2]
HEADER: Final = ROOT / "include" / "fmv" / "menuart.h"
TILES: Final = (
    ("TOP", "panel_top"),
    ("PANEL", "panel"),
    ("CAP_LEFT", "bar_cap_left"),
    ("CAP_RIGHT", "bar_cap_right"),
    ("FILLED", "bar_filled"),
    ("EMPTY", "bar_empty"),
    ("KNOB", "bar_knob"),
)
PLANES: Final = 4
TILE_BYTES: Final = font.SIZE * PLANES


def planar_row(indices: list[int]) -> list[int]:
    return [
        sum(((index >> plane) & 1) << (font.SIZE - 1 - x) for x, index in enumerate(indices))
        for plane in range(PLANES)
    ]


def tile_bytes(name: str) -> bytes:
    rows = font.glyph_art()[name]
    return bytes(
        value for row in rows for value in planar_row([menu.INDEX_OF[code] for code in row])
    )


def header() -> str:
    lines = [
        "#ifndef FMV_MENUART_H",
        "#define FMV_MENUART_H",
        "",
        '#include "fmv/types.h"',
        "",
        f"#define FMV_MENU_ART_TILES {len(TILES)}u",
        f"#define FMV_MENU_ART_BYTES {TILE_BYTES}u",
        *(f"#define FMV_MENU_ART_{label} {index}u" for index, (label, _) in enumerate(TILES)),
        "",
        "static const u8 fmv_menu_art[FMV_MENU_ART_TILES][FMV_MENU_ART_BYTES] = {",
        *(f"    {{{', '.join(f'0x{b:02X}u' for b in tile_bytes(name))}}}," for _, name in TILES),
        "};",
        "",
        "#endif",
    ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="menu_art")
    parser.add_argument("--out", type=Path, default=HEADER)
    args = parser.parse_args(argv)
    args.out.write_text(header())
    return 0


if __name__ == "__main__":
    sys.exit(main())
