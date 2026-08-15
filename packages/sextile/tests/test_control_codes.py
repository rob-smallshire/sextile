"""Teletext spacing attributes.

Every one of these occupies a character cell, displayed as a space. That is the
fact the layout engine is built around: a colour change costs a column out of the
forty available, so colour cannot be bolted on afterwards.
"""

import pytest

from sextile.viewdata.controls import (
    Attribute,
    Colour,
    alpha_colour,
    graphics_colour,
    is_attribute_code,
)


class TestColour:
    """The eight teletext colours, in their canonical order."""

    @pytest.mark.parametrize(
        ("colour", "value"),
        [
            (Colour.BLACK, 0),
            (Colour.RED, 1),
            (Colour.GREEN, 2),
            (Colour.YELLOW, 3),
            (Colour.BLUE, 4),
            (Colour.MAGENTA, 5),
            (Colour.CYAN, 6),
            (Colour.WHITE, 7),
        ],
    )
    def test_colour_ordering(self, colour: Colour, value: int) -> None:
        assert colour == value

    def test_there_are_eight_colours(self) -> None:
        assert len(Colour) == 8


class TestControlCodes:
    @pytest.mark.parametrize(
        ("control", "value"),
        [
            (Attribute.ALPHA_RED, 0x01),
            (Attribute.ALPHA_GREEN, 0x02),
            (Attribute.ALPHA_YELLOW, 0x03),
            (Attribute.ALPHA_BLUE, 0x04),
            (Attribute.ALPHA_MAGENTA, 0x05),
            (Attribute.ALPHA_CYAN, 0x06),
            (Attribute.ALPHA_WHITE, 0x07),
            (Attribute.FLASH, 0x08),
            (Attribute.STEADY, 0x09),
            (Attribute.END_BOX, 0x0A),
            (Attribute.START_BOX, 0x0B),
            (Attribute.NORMAL_HEIGHT, 0x0C),
            (Attribute.DOUBLE_HEIGHT, 0x0D),
            (Attribute.GRAPHICS_RED, 0x11),
            (Attribute.GRAPHICS_GREEN, 0x12),
            (Attribute.GRAPHICS_YELLOW, 0x13),
            (Attribute.GRAPHICS_BLUE, 0x14),
            (Attribute.GRAPHICS_MAGENTA, 0x15),
            (Attribute.GRAPHICS_CYAN, 0x16),
            (Attribute.GRAPHICS_WHITE, 0x17),
            (Attribute.CONCEAL, 0x18),
            (Attribute.CONTIGUOUS_GRAPHICS, 0x19),
            (Attribute.SEPARATED_GRAPHICS, 0x1A),
            (Attribute.BLACK_BACKGROUND, 0x1C),
            (Attribute.NEW_BACKGROUND, 0x1D),
            (Attribute.HOLD_GRAPHICS, 0x1E),
            (Attribute.RELEASE_GRAPHICS, 0x1F),
        ],
    )
    def test_control_code_values(self, control: Attribute, value: int) -> None:
        assert control == value

    @pytest.mark.parametrize("control", list(Attribute))
    def test_all_controls_lie_in_the_control_range(self, control: Attribute) -> None:
        assert 0x00 <= control <= 0x1F

    @pytest.mark.parametrize("code", [0x00, 0x01, 0x1F])
    def test_recognises_control_codes(self, code: int) -> None:
        assert is_attribute_code(code)

    @pytest.mark.parametrize("code", [0x20, 0x41, 0x7F, 0x80])
    def test_rejects_non_control_codes(self, code: int) -> None:
        assert not is_attribute_code(code)


class TestColourSelection:
    @pytest.mark.parametrize(
        ("colour", "control"),
        [
            (Colour.RED, Attribute.ALPHA_RED),
            (Colour.GREEN, Attribute.ALPHA_GREEN),
            (Colour.YELLOW, Attribute.ALPHA_YELLOW),
            (Colour.BLUE, Attribute.ALPHA_BLUE),
            (Colour.MAGENTA, Attribute.ALPHA_MAGENTA),
            (Colour.CYAN, Attribute.ALPHA_CYAN),
            (Colour.WHITE, Attribute.ALPHA_WHITE),
        ],
    )
    def test_alpha_colour_selection(self, colour: Colour, control: Attribute) -> None:
        assert alpha_colour(colour) == control

    @pytest.mark.parametrize(
        ("colour", "control"),
        [
            (Colour.RED, Attribute.GRAPHICS_RED),
            (Colour.GREEN, Attribute.GRAPHICS_GREEN),
            (Colour.YELLOW, Attribute.GRAPHICS_YELLOW),
            (Colour.BLUE, Attribute.GRAPHICS_BLUE),
            (Colour.MAGENTA, Attribute.GRAPHICS_MAGENTA),
            (Colour.CYAN, Attribute.GRAPHICS_CYAN),
            (Colour.WHITE, Attribute.GRAPHICS_WHITE),
        ],
    )
    def test_graphics_colour_selection(self, colour: Colour, control: Attribute) -> None:
        assert graphics_colour(colour) == control

    def test_black_foreground_is_unavailable_as_a_spacing_attribute(self) -> None:
        #  0x00 and 0x10 are reserved on the transmission path, so black text can
        #  only be had via a background change. Refusing here stops a caller
        #  silently producing invisible text.
        with pytest.raises(ValueError, match="black"):
            alpha_colour(Colour.BLACK)
        with pytest.raises(ValueError, match="black"):
            graphics_colour(Colour.BLACK)
