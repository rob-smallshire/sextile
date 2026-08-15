"""Turning characters and attributes into bytes for a viewdata terminal.

Every expectation here was measured against Commstar in Prestel mode; see
docs/viewdata-encoding.md. The central fact is that the wire carries two
separate namespaces: a bare C0 byte controls the screen, while an attribute
must be escaped as ESC followed by the code plus 0x40.
"""

import pytest

from sextile.viewdata.controls import Attribute, Colour, alpha_colour, graphics_colour
from sextile.viewdata.encoding import (
    ESCAPE,
    ScreenControl,
    encode_attribute,
    encode_text,
)


class TestAttributeEncoding:
    def test_alpha_red_is_escape_forty_one(self) -> None:
        #  The measurement: ESC 0x41 produced a control cell reading 0x01, red.
        assert encode_attribute(Attribute.ALPHA_RED) == bytes([0x1B, 0x41])

    @pytest.mark.parametrize(
        ("control", "expected"),
        [
            (Attribute.ALPHA_RED, b"\x1bA"),
            (Attribute.ALPHA_GREEN, b"\x1bB"),
            (Attribute.ALPHA_WHITE, b"\x1bG"),
            (Attribute.FLASH, b"\x1bH"),
            (Attribute.DOUBLE_HEIGHT, b"\x1bM"),
            (Attribute.GRAPHICS_WHITE, b"\x1bW"),
            (Attribute.CONTIGUOUS_GRAPHICS, b"\x1bY"),
            (Attribute.SEPARATED_GRAPHICS, b"\x1bZ"),
            (Attribute.NEW_BACKGROUND, b"\x1b]"),
        ],
    )
    def test_measured_encodings(self, control: Attribute, expected: bytes) -> None:
        assert encode_attribute(control) == expected

    @pytest.mark.parametrize("control", list(Attribute))
    def test_every_attribute_is_two_bytes_led_by_escape(self, control: Attribute) -> None:
        encoded = encode_attribute(control)
        assert len(encoded) == 2
        assert encoded[0] == ESCAPE
        assert encoded[1] == control + 0x40

    @pytest.mark.parametrize("control", list(Attribute))
    def test_no_attribute_encodes_into_the_c0_range(self, control: Attribute) -> None:
        #  An attribute byte that landed in C0 would be read as screen control.
        assert encode_attribute(control)[1] >= 0x20

    def test_colour_selection_round_trips_through_encoding(self) -> None:
        assert encode_attribute(alpha_colour(Colour.CYAN)) == b"\x1bF"
        assert encode_attribute(graphics_colour(Colour.CYAN)) == b"\x1bV"


class TestScreenControl:
    """The bare C0 codes, which mean something entirely different from attributes."""

    @pytest.mark.parametrize(
        ("control", "value"),
        [
            (ScreenControl.CLEAR_SCREEN, 0x0C),
            (ScreenControl.CURSOR_HOME, 0x1E),
            (ScreenControl.CARRIAGE_RETURN, 0x0D),
            (ScreenControl.LINE_FEED, 0x0A),
        ],
    )
    def test_measured_values(self, control: ScreenControl, value: int) -> None:
        assert control == value

    @pytest.mark.parametrize(
        ("control", "value"),
        [
            (ScreenControl.CURSOR_UP, 0x0B),
            (ScreenControl.CURSOR_RIGHT, 0x09),
            (ScreenControl.CURSOR_ON, 0x11),
            (ScreenControl.CURSOR_OFF, 0x14),
        ],
    )
    def test_the_cursor_codes(self, control: ScreenControl, value: int) -> None:
        assert control == value

    def test_no_screen_control_is_ever_escaped(self) -> None:
        #  Escaping one would turn it into an attribute: 0x11 escaped is
        #  graphics red, and 0x14 graphics blue. The two namespaces are what
        #  keep those apart.
        for control in ScreenControl:
            assert encode_attribute(Attribute(control))[1] != control

    def test_clear_screen_collides_with_normal_height_but_differs_on_the_wire(self) -> None:
        #  Both are 0x0C; only the escape tells them apart. This is the mistake
        #  the two namespaces exist to prevent.
        assert int(ScreenControl.CLEAR_SCREEN) == int(Attribute.NORMAL_HEIGHT)
        assert bytes([ScreenControl.CLEAR_SCREEN]) != encode_attribute(Attribute.NORMAL_HEIGHT)


class TestTextEncoding:
    def test_plain_text(self) -> None:
        assert encode_text("STARDOT") == b"STARDOT"

    def test_pound_sign_becomes_0x23(self) -> None:
        assert encode_text("£5") == bytes([0x23]) + b"5"

    def test_hash_becomes_0x5f(self) -> None:
        assert encode_text("#") == bytes([0x5F])

    def test_unrepresentable_characters_are_transliterated_first(self) -> None:
        assert encode_text("café") == b"cafe"
        assert encode_text("{x}") == b"(x)"

    def test_emoji_becomes_a_question_mark(self) -> None:
        assert encode_text("\U0001f600") == b"?"

    @pytest.mark.parametrize(
        "text",
        [
            "",
            "The quick brown fox",
            "“Posted by Iapetus — Sun Aug 02, 2026”",
            "C:\\BEEB\\*.SSD £10 ½",
            "".join(chr(code) for code in range(0x00, 0x0400)),
        ],
    )
    def test_no_byte_ever_lands_in_the_control_range(self, text: str) -> None:
        #  Text that emitted a C0 byte would move the cursor or clear the screen.
        assert all(byte >= 0x20 for byte in encode_text(text))

    @pytest.mark.parametrize("text", ["A", "£", "#", "½ ¼ ¾ ÷ ← → ↑"])
    def test_every_byte_is_seven_bit(self, text: str) -> None:
        #  Prestel mode runs at 7E1; an eighth bit cannot survive the line.
        assert all(byte < 0x80 for byte in encode_text(text))
