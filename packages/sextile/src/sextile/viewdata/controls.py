"""Teletext spacing attributes and the eight teletext colours.

Spacing attributes occupy positions 0x00-0x1F. Each one takes a character cell of
its own, displayed as a space in the prevailing background colour. That cost is
what forces the layout engine to be attribute-aware: a line of forty columns that
changes colour twice has only thirty-eight columns left for text.

Positions 0x00 and 0x10 nominally select black alphanumerics and black graphics,
but are not usable as transmitted attributes, so they are absent here. Black text
is obtained by changing the background instead.
"""

from enum import IntEnum
from typing import Final

__all__ = [
    "ALPHA_COLOURS",
    "GRAPHICS_COLOURS",
    "Colour",
    "Attribute",
    "alpha_colour",
    "colour_of",
    "graphics_colour",
    "is_attribute_code",
]


class Colour(IntEnum):
    """The eight teletext colours, in their canonical order."""

    BLACK = 0
    RED = 1
    GREEN = 2
    YELLOW = 3
    BLUE = 4
    MAGENTA = 5
    CYAN = 6
    WHITE = 7


class Attribute(IntEnum):
    """Teletext spacing attributes."""

    ALPHA_RED = 0x01
    ALPHA_GREEN = 0x02
    ALPHA_YELLOW = 0x03
    ALPHA_BLUE = 0x04
    ALPHA_MAGENTA = 0x05
    ALPHA_CYAN = 0x06
    ALPHA_WHITE = 0x07
    FLASH = 0x08
    STEADY = 0x09
    END_BOX = 0x0A
    START_BOX = 0x0B
    NORMAL_HEIGHT = 0x0C
    DOUBLE_HEIGHT = 0x0D
    GRAPHICS_RED = 0x11
    GRAPHICS_GREEN = 0x12
    GRAPHICS_YELLOW = 0x13
    GRAPHICS_BLUE = 0x14
    GRAPHICS_MAGENTA = 0x15
    GRAPHICS_CYAN = 0x16
    GRAPHICS_WHITE = 0x17
    CONCEAL = 0x18
    CONTIGUOUS_GRAPHICS = 0x19
    SEPARATED_GRAPHICS = 0x1A
    BLACK_BACKGROUND = 0x1C
    NEW_BACKGROUND = 0x1D
    HOLD_GRAPHICS = 0x1E
    RELEASE_GRAPHICS = 0x1F


FIRST_ATTRIBUTE: Final = 0x00
LAST_ATTRIBUTE: Final = 0x1F

_ALPHA_COLOUR_BASE: Final = 0x00
_GRAPHICS_COLOUR_BASE: Final = 0x10

#: The spacing attributes that select a foreground colour, stated once here so a
#: reader of a frame does not respell the ranges. Alpha runs 0x01-0x07 and
#: graphics 0x11-0x17; black has no colour attribute and is in neither.
ALPHA_COLOURS: Final = range(_ALPHA_COLOUR_BASE + 1, _ALPHA_COLOUR_BASE + 8)
GRAPHICS_COLOURS: Final = range(_GRAPHICS_COLOUR_BASE + 1, _GRAPHICS_COLOUR_BASE + 8)


def colour_of(code: int) -> Colour | None:
    """The colour a spacing attribute selects, or None if it selects none.

    The inverse of `alpha_colour` and `graphics_colour`: both the alpha and the
    graphics colour attributes pick the same eight colours, and this reads either
    back. No code returns black, black having no colour attribute.
    """
    if code in ALPHA_COLOURS:
        return Colour(code - _ALPHA_COLOUR_BASE)
    if code in GRAPHICS_COLOURS:
        return Colour(code - _GRAPHICS_COLOUR_BASE)
    return None


def is_attribute_code(code: int) -> bool:
    """Say whether a code position holds a spacing attribute.

    Args:
        code: A code position from a frame, between 0 and 127.

    Returns:
        True where the position is one of the attributes that select a colour
        or a character set, and False where it is a character the SAA5050
        displays. An attribute occupies a cell and shows as a blank, so a
        caller counting what a row says has to tell the two apart.
    """
    return FIRST_ATTRIBUTE <= code <= LAST_ATTRIBUTE


def alpha_colour(colour: Colour) -> Attribute:
    """The spacing attribute selecting alphanumeric text in a colour."""
    _reject_black(colour)
    return Attribute(_ALPHA_COLOUR_BASE + colour)


def graphics_colour(colour: Colour) -> Attribute:
    """The spacing attribute selecting mosaic graphics in a colour."""
    _reject_black(colour)
    return Attribute(_GRAPHICS_COLOUR_BASE + colour)


def _reject_black(colour: Colour) -> None:
    if colour is Colour.BLACK:
        raise ValueError(
            "There is no usable spacing attribute for black foreground; "
            "change the background colour instead"
        )
