"""The teletext G0 character set as displayed by the SAA5050 in BBC Mode 7.

G0 is emphatically not ASCII. Thirteen positions carry English national-option
characters, and the two that matter most are transposed relative to what a modern
programmer expects: a pound sign occupies 0x23, and the hash -- the viewdata command
key, so a mistake here is visible on the very first frame -- lives at 0x5F.
"""

import pytest

from sextile.viewdata.ansi import mosaic_character, sextant
from sextile.viewdata.charset import (
    G0_TO_UNICODE,
    UNICODE_TO_G0,
    decode_g0,
    encode_g0,
    is_representable,
    mosaic_code,
    mosaic_pattern,
)

PRINTABLE_POSITIONS = range(0x20, 0x80)

#  The English national-option positions, per ETS 300 706.
NATIONAL_OPTIONS = [
    (0x23, "£"),  # POUND SIGN
    (0x24, "$"),
    (0x40, "@"),
    (0x5B, "←"),  # LEFTWARDS ARROW
    (0x5C, "½"),  # VULGAR FRACTION ONE HALF
    (0x5D, "→"),  # RIGHTWARDS ARROW
    (0x5E, "↑"),  # UPWARDS ARROW
    (0x5F, "#"),
    (0x60, "―"),  # HORIZONTAL BAR
    (0x7B, "¼"),  # VULGAR FRACTION ONE QUARTER
    (0x7C, "‖"),  # DOUBLE VERTICAL LINE
    (0x7D, "¾"),  # VULGAR FRACTION THREE QUARTERS
    (0x7E, "÷"),  # DIVISION SIGN
    (0x7F, "▮"),  # BLACK VERTICAL RECTANGLE
]

#  Characters a modern keyboard offers that G0 simply does not have. Source code
#  quoted in forum posts will hit these constantly, so they must fail loudly here
#  and be handled deliberately by the transliteration layer rather than silently
#  rendering as arrows and fractions.
ABSENT_FROM_G0 = ["[", "\\", "]", "^", "_", "`", "{", "|", "}", "~"]


def test_pound_sign_occupies_0x23() -> None:
    assert encode_g0("£") == 0x23


def test_hash_occupies_0x5f() -> None:
    assert encode_g0("#") == 0x5F


def test_space_occupies_0x20() -> None:
    assert encode_g0(" ") == 0x20


@pytest.mark.parametrize("character", "ABCXYZabcxyz0123456789")
def test_letters_and_digits_agree_with_ascii(character: str) -> None:
    assert encode_g0(character) == ord(character)


@pytest.mark.parametrize("character", "!\"$%&'()*+,-./:;<=>?@")
def test_common_punctuation_agrees_with_ascii(character: str) -> None:
    assert encode_g0(character) == ord(character)


@pytest.mark.parametrize(("position", "character"), NATIONAL_OPTIONS)
def test_national_option_positions(position: int, character: str) -> None:
    assert decode_g0(position) == character


def test_table_covers_every_printable_position() -> None:
    assert set(G0_TO_UNICODE) == set(PRINTABLE_POSITIONS)


def test_table_is_a_bijection() -> None:
    characters = list(G0_TO_UNICODE.values())
    assert len(set(characters)) == len(characters)
    inverted = {character: position for position, character in G0_TO_UNICODE.items()}
    assert inverted == UNICODE_TO_G0


@pytest.mark.parametrize("position", PRINTABLE_POSITIONS)
def test_every_position_round_trips(position: int) -> None:
    assert encode_g0(decode_g0(position)) == position


@pytest.mark.parametrize("character", ABSENT_FROM_G0)
def test_characters_absent_from_g0_are_not_representable(character: str) -> None:
    assert not is_representable(character)
    assert encode_g0(character) is None


@pytest.mark.parametrize(("position", "character"), NATIONAL_OPTIONS)
def test_national_option_characters_are_representable(position: int, character: str) -> None:
    assert is_representable(character)


@pytest.mark.parametrize("position", [-1, 0x00, 0x1F, 0x80, 0xFF])
def test_positions_outside_the_printable_range_are_rejected(position: int) -> None:
    with pytest.raises(ValueError):
        decode_g0(position)


def test_encoding_requires_a_single_character() -> None:
    with pytest.raises(ValueError):
        encode_g0("ab")


class TestMosaicCodes:
    """The 2x3 blocks a mosaic character draws, and the byte that draws them.

    The layout is read from Beebium's `get_graphics_row`: five blocks in bits
    0-4 and the sixth in bit 6, because bit 5 is spent saying "this is a mosaic
    and not a control".
    """

    def test_no_blocks_is_the_space_of_the_mosaic_range(self) -> None:
        assert mosaic_code(0b000000) == 0x20

    def test_all_six_blocks_is_the_character_the_rules_use(self) -> None:
        assert mosaic_code(0b111111) == 0x7F

    def test_the_sixth_block_skips_the_range_bit(self) -> None:
        #  Bottom-right is bit 6 on the wire, not bit 5.
        assert mosaic_code(0b100000) == 0x60

    @pytest.mark.parametrize("pattern", range(64))
    def test_every_pattern_survives_the_round_trip(self, pattern: int) -> None:
        assert mosaic_pattern(mosaic_code(pattern)) == pattern

    @pytest.mark.parametrize("pattern", range(64))
    def test_every_code_lands_where_mosaics_live(self, pattern: int) -> None:
        code = mosaic_code(pattern)
        assert 0x20 <= code <= 0x3F or 0x60 <= code <= 0x7F

    def test_a_pattern_of_more_than_six_bits_is_refused(self) -> None:
        with pytest.raises(ValueError):
            mosaic_code(64)

    def test_it_agrees_with_the_preview(self) -> None:
        #  Both name the blocks in the same order, so a frame drawn by one is
        #  read correctly by the other.
        assert sextant(0b000001) == mosaic_character(mosaic_code(0b000001))
