"""Showing a frame in a modern terminal, so development needs no Beeb.

Teletext graphics characters are 2x3 grids of blocks encoded in the bits of the
character code. Unicode's Symbols for Legacy Computing block covers every one of
those 64 patterns, so a frame can be shown as the SAA5050 would actually draw it
rather than approximated with punctuation.

Separated graphics are drawn here as contiguous: Unicode has no separated
variants, and the difference is decorative rather than structural.
"""

from typing import Final

from sextile.viewdata.charset import decode_g0, mosaic_pattern
from sextile.viewdata.controls import GRAPHICS_COLOURS, Attribute, Colour, colour_of
from sextile.viewdata.frame import COLUMNS, ROWS, Frame

#  Patterns Unicode already had before the sextant block was added, which the
#  sextant block therefore skips.
_PRE_EXISTING: Final[dict[int, str]] = {
    0b000000: " ",
    0b010101: "▌",  # LEFT HALF BLOCK
    0b101010: "▐",  # RIGHT HALF BLOCK
    0b111111: "█",  # FULL BLOCK
}

_SEXTANT_BASE: Final = 0x1FB00

#  Teletext colour index to ANSI bright foreground and background.
_ANSI_FOREGROUND: Final = [30, 91, 92, 93, 94, 95, 96, 97]
_ANSI_BACKGROUND: Final = [40, 101, 102, 103, 104, 105, 106, 107]


def sextant(pattern: int) -> str:
    """The Unicode character drawing a 2x3 block pattern.

    Bits from least to most significant are top-left, top-right, middle-left,
    middle-right, bottom-left, bottom-right.
    """
    if not 0 <= pattern < 64:
        raise ValueError(f"a sextant pattern is six bits, got {pattern}")
    if pattern in _PRE_EXISTING:
        return _PRE_EXISTING[pattern]
    skipped = sum(1 for existing in _PRE_EXISTING if existing < pattern)
    return chr(_SEXTANT_BASE + pattern - skipped)


def mosaic_character(code: int) -> str:
    """How a character code displays while graphics are selected.

    Codes 0x40-0x5F still show alphanumerics; everything else is a mosaic.
    """
    if not 0x20 <= code <= 0x7F:
        raise ValueError(f"0x{code:02X} is not a displayable character code")
    if 0x40 <= code <= 0x5F:
        return decode_g0(code)
    return sextant(mosaic_pattern(code))


def render_ansi(frame: Frame, *, colour: bool = True) -> str:
    """A frame as lines of text, optionally with ANSI colour."""
    return "\n".join(_render_row(frame, row, colour) for row in range(ROWS))


def _render_row(frame: Frame, row: int, colour: bool) -> str:
    #  Attributes reset at the start of every row.
    foreground = Colour.WHITE
    background = Colour.BLACK
    graphics = False
    held: list[str] = []
    if colour:
        held.append(_ansi(foreground, background))

    for column in range(COLUMNS):
        code = frame.cell(row, column)
        if frame.is_attribute(row, column):
            #  The attribute cell itself displays as a space in the prevailing
            #  background; the change applies from the following cell.
            held.append(" ")
            found = colour_of(code)
            if found is not None:
                foreground = found
                graphics = code in GRAPHICS_COLOURS
            elif code == Attribute.BLACK_BACKGROUND:
                background = Colour.BLACK
            elif code == Attribute.NEW_BACKGROUND:
                background = foreground
            if colour:
                held.append(_ansi(foreground, background))
            continue
        held.append(mosaic_character(code) if graphics else decode_g0(code))

    if colour:
        held.append("\x1b[0m")
    return "".join(held)


def _ansi(foreground: Colour, background: Colour) -> str:
    return f"\x1b[{_ANSI_FOREGROUND[foreground]};{_ANSI_BACKGROUND[background]}m"
