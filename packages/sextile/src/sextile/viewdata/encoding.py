"""Bytes for a viewdata terminal.

The wire carries two namespaces that share the C0 range, and telling them apart
is the whole job of this module:

- a **bare C0 byte** controls the screen -- clear, home, carriage return, line feed;
- an **escaped byte**, ESC followed by the code plus 0x40, is a teletext spacing
  attribute.

So 0x0C alone clears the screen while ``ESC 0x4C`` selects normal height, even
though both attributes are 0x0C. Confusing them yields a display wrong in ways
that look like transport corruption.

There is deliberately no option to send the SAA5050's codes directly as
0x80-0x9F. Prestel mode runs the line at 7E1, which has no eighth bit to carry
them: measured against Commstar, such bytes vanish entirely. See
docs/viewdata-encoding.md.
"""

from enum import IntEnum
from typing import Final

from sextile.content.transliterate import transliterate
from sextile.viewdata.charset import encode_g0
from sextile.viewdata.controls import Attribute

__all__ = [
    "ESCAPE",
    "ScreenControl",
    "encode_attribute",
    "encode_text",
]

ESCAPE: Final = 0x1B

#  Attributes are transmitted shifted out of the C0 range, which is what lets the
#  bare C0 codes keep their own meaning.
_ESCAPE_OFFSET: Final = 0x40


class ScreenControl(IntEnum):
    """Bare C0 codes controlling the screen, measured against Commstar.

    All of these are known to be consumed as controls rather than displayed --
    `0x11 A B 0x14 C D` renders as `ABCD` with no gap, so neither takes a cell.

    CURSOR_ON and CURSOR_OFF follow viewdata convention, and were confirmed on
    a real screen rather than by reading it back: the cursor flashes, so a
    single sample tells you only which half of the blink you caught.
    """

    LINE_FEED = 0x0A
    CARRIAGE_RETURN = 0x0D
    CLEAR_SCREEN = 0x0C
    CURSOR_HOME = 0x1E
    CURSOR_UP = 0x0B
    CURSOR_LEFT = 0x08
    CURSOR_RIGHT = 0x09
    CURSOR_ON = 0x11
    CURSOR_OFF = 0x14


def encode_attribute(attribute: Attribute) -> bytes:
    """The two bytes transmitting a teletext spacing attribute."""
    return bytes([ESCAPE, attribute + _ESCAPE_OFFSET])


def encode_text(text: str) -> bytes:
    """Transliterate text and encode it in the G0 repertoire.

    Every byte returned is a displayable character: transliteration guarantees
    the result is representable, so nothing can stray into the attribute range and
    move the cursor by accident.
    """
    encoded = bytearray()
    for character in transliterate(text):
        position = encode_g0(character)
        if position is None:  # pragma: no cover - transliteration is total
            raise AssertionError(f"transliteration produced unrepresentable {character!r}")
        encoded.append(position)
    return bytes(encoded)
