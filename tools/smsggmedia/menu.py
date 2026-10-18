from __future__ import annotations

from typing import Final

import numpy as np
import numpy.typing as npt
from fmvcore import font

from smsggmedia import lattice, smscolor

ORDER: Final = (font.PANEL, font.INK, font.ACCENT, font.DIM)
FILM_ENTRIES: Final = smscolor.PALETTE_ENTRIES - len(ORDER)
ENTRIES: Final = tuple(range(FILM_ENTRIES, smscolor.PALETTE_ENTRIES))
TRANSPARENT: Final = " "
INDEX_OF: Final = {
    **dict(zip(ORDER, ENTRIES, strict=True)),
    font.EDGE: ENTRIES[ORDER.index(font.DIM)],
    TRANSPARENT: 0,
}
MENU_PALETTE: Final = 1


def colours(space: lattice.Lattice) -> npt.NDArray[np.unsignedinteger]:
    levels = np.array([font.MENU_COLOURS[code] for code in ORDER], dtype=np.float64)
    scaled = np.rint(levels * space.top / font.MENU_LEVELS).astype(np.uint8)
    return space.pack(scaled)
