"""Teletext spacing attributes.

Every one of these occupies a character cell, displayed as a space. That is the
fact the layout engine is built around: a colour change costs a column out of the
forty available, so colour cannot be bolted on afterwards.
"""

import pytest

from sextile.viewdata.controls import (
    Colour,
    Control,
    alpha_colour,
    graphics_colour,
    is_control_code,
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
            (Control.ALPHA_RED, 0x01),
            (Control.ALPHA_GREEN, 0x02),
            (Control.ALPHA_YELLOW, 0x03),
            (Control.ALPHA_BLUE, 0x04),
            (Control.ALPHA_MAGENTA, 0x05),
            (Control.ALPHA_CYAN, 0x06),
            (Control.ALPHA_WHITE, 0x07),
            (Control.FLASH, 0x08),
            (Control.STEADY, 0x09),
            (Control.END_BOX, 0x0A),
            (Control.START_BOX, 0x0B),
            (Control.NORMAL_HEIGHT, 0x0C),
            (Control.DOUBLE_HEIGHT, 0x0D),
            (Control.GRAPHICS_RED, 0x11),
            (Control.GRAPHICS_GREEN, 0x12),
            (Control.GRAPHICS_YELLOW, 0x13),
            (Control.GRAPHICS_BLUE, 0x14),
            (Control.GRAPHICS_MAGENTA, 0x15),
            (Control.GRAPHICS_CYAN, 0x16),
            (Control.GRAPHICS_WHITE, 0x17),
            (Control.CONCEAL, 0x18),
            (Control.CONTIGUOUS_GRAPHICS, 0x19),
            (Control.SEPARATED_GRAPHICS, 0x1A),
            (Control.BLACK_BACKGROUND, 0x1C),
            (Control.NEW_BACKGROUND, 0x1D),
            (Control.HOLD_GRAPHICS, 0x1E),
            (Control.RELEASE_GRAPHICS, 0x1F),
        ],
    )
    def test_control_code_values(self, control: Control, value: int) -> None:
        assert control == value

    @pytest.mark.parametrize("control", list(Control))
    def test_all_controls_lie_in_the_control_range(self, control: Control) -> None:
        assert 0x00 <= control <= 0x1F

    @pytest.mark.parametrize("code", [0x00, 0x01, 0x1F])
    def test_recognises_control_codes(self, code: int) -> None:
        assert is_control_code(code)

    @pytest.mark.parametrize("code", [0x20, 0x41, 0x7F, 0x80])
    def test_rejects_non_control_codes(self, code: int) -> None:
        assert not is_control_code(code)


class TestColourSelection:
    @pytest.mark.parametrize(
        ("colour", "control"),
        [
            (Colour.RED, Control.ALPHA_RED),
            (Colour.GREEN, Control.ALPHA_GREEN),
            (Colour.YELLOW, Control.ALPHA_YELLOW),
            (Colour.BLUE, Control.ALPHA_BLUE),
            (Colour.MAGENTA, Control.ALPHA_MAGENTA),
            (Colour.CYAN, Control.ALPHA_CYAN),
            (Colour.WHITE, Control.ALPHA_WHITE),
        ],
    )
    def test_alpha_colour_selection(self, colour: Colour, control: Control) -> None:
        assert alpha_colour(colour) == control

    @pytest.mark.parametrize(
        ("colour", "control"),
        [
            (Colour.RED, Control.GRAPHICS_RED),
            (Colour.GREEN, Control.GRAPHICS_GREEN),
            (Colour.YELLOW, Control.GRAPHICS_YELLOW),
            (Colour.BLUE, Control.GRAPHICS_BLUE),
            (Colour.MAGENTA, Control.GRAPHICS_MAGENTA),
            (Colour.CYAN, Control.GRAPHICS_CYAN),
            (Colour.WHITE, Control.GRAPHICS_WHITE),
        ],
    )
    def test_graphics_colour_selection(self, colour: Colour, control: Control) -> None:
        assert graphics_colour(colour) == control

    def test_black_foreground_is_unavailable_as_a_spacing_attribute(self) -> None:
        #  0x00 and 0x10 are reserved on the transmission path, so black text can
        #  only be had via a background change. Refusing here stops a caller
        #  silently producing invisible text.
        with pytest.raises(ValueError, match="black"):
            alpha_colour(Colour.BLACK)
        with pytest.raises(ValueError, match="black"):
            graphics_colour(Colour.BLACK)
