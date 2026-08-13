r"""The teletext G0 character set displayed by the SAA5050 in BBC Mode 7.

G0 occupies positions 0x20-0x7F and coincides with ASCII everywhere except the
thirteen national-option positions, which here take their English values per
ETS 300 706. Two of those transpositions bite immediately: 0x23 displays a pound
sign rather than a hash, and the hash -- the viewdata command key -- sits at 0x5F.

Ten characters a modern keyboard offers have no G0 representation at all:
``[ \ ] ^ _ ` { | } ~``. Those positions are occupied by arrows, fractions and
rules instead. Quoted source code meets them constantly, so
``encode_g0`` reports them as unrepresentable rather than guessing; deciding what
to show in their place belongs to the transliteration layer.
"""

from typing import Final

FIRST_PRINTABLE: Final = 0x20
LAST_PRINTABLE: Final = 0x7F

#  Positions where English G0 departs from ASCII. Everything else is ASCII.
_ENGLISH_NATIONAL_OPTIONS: Final[dict[int, str]] = {
    0x23: "£",  # POUND SIGN, in place of NUMBER SIGN
    0x5B: "←",  # LEFTWARDS ARROW
    0x5C: "½",  # VULGAR FRACTION ONE HALF
    0x5D: "→",  # RIGHTWARDS ARROW
    0x5E: "↑",  # UPWARDS ARROW
    0x5F: "#",  # NUMBER SIGN, in place of LOW LINE
    0x60: "―",  # HORIZONTAL BAR, in place of GRAVE ACCENT
    0x7B: "¼",  # VULGAR FRACTION ONE QUARTER
    0x7C: "‖",  # DOUBLE VERTICAL LINE
    0x7D: "¾",  # VULGAR FRACTION THREE QUARTERS
    0x7E: "÷",  # DIVISION SIGN
    0x7F: "▮",  # BLACK VERTICAL RECTANGLE
}

G0_TO_UNICODE: Final[dict[int, str]] = {
    position: _ENGLISH_NATIONAL_OPTIONS.get(position, chr(position))
    for position in range(FIRST_PRINTABLE, LAST_PRINTABLE + 1)
}

UNICODE_TO_G0: Final[dict[str, int]] = {
    character: position for position, character in G0_TO_UNICODE.items()
}


def decode_g0(position: int) -> str:
    """The Unicode character displayed at a G0 code position."""
    try:
        return G0_TO_UNICODE[position]
    except KeyError:
        raise ValueError(
            f"0x{position:02X} is outside the printable G0 range "
            f"0x{FIRST_PRINTABLE:02X}-0x{LAST_PRINTABLE:02X}"
        ) from None


#  A mosaic character carries five of its six blocks in bits 0-4 and the sixth
#  in bit 6, because bit 5 is spent saying "this is a mosaic and not a control".
#  Read from Beebium's `TeletextFontInit::get_graphics_row`, which masks
#  0x01/0x02 for the top pair, 0x04/0x08 for the middle and 0x10/0x40 for the
#  bottom -- so the codes land in 0x20-0x3F and 0x60-0x7F.
_MOSAIC_RANGE: Final = 0x20
_SIXTH_BLOCK: Final = 0x40


def mosaic_code(pattern: int) -> int:
    """The character code drawing a 2x3 block pattern.

    Bits from least to most significant are top-left, top-right, middle-left,
    middle-right, bottom-left, bottom-right -- the order `sextant` uses, so the
    two agree about which block is which.
    """
    if not 0 <= pattern < 64:
        raise ValueError(f"a mosaic pattern is six bits, got {pattern}")
    return _MOSAIC_RANGE | (pattern & 0x1F) | ((pattern & 0x20) << 1)


def mosaic_pattern(code: int) -> int:
    """The 2x3 block pattern a character code draws, while graphics are on."""
    return (code & 0x1F) | ((code & _SIXTH_BLOCK) >> 1)


def encode_g0(character: str) -> int | None:
    """The G0 code position displaying a character, or None if G0 cannot show it."""
    if len(character) != 1:
        raise ValueError(f"Expected a single character, got {character!r}")
    return UNICODE_TO_G0.get(character)


def is_representable(character: str) -> bool:
    """Whether G0 can display a character directly, without transliteration."""
    return encode_g0(character) is not None
