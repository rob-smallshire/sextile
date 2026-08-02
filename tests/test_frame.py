"""A viewdata frame: 24 rows of 40 cells, each holding a character or an attribute.

The geometry is measured, not assumed -- see docs/viewdata-encoding.md. Commstar
wraps from the bottom right cell back to the top left rather than scrolling, so a
frame that emitted even one cell too many would corrupt the top of the frame it
had just drawn. Making the grid fixed-size removes that failure entirely.
"""

import pytest

from sextile.viewdata.controls import Colour, Control, alpha_colour
from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import COLUMNS, ROWS, Frame

SPACE = 0x20


class TestGeometry:
    def test_a_frame_is_24_by_40(self) -> None:
        assert (ROWS, COLUMNS) == (24, 40)

    def test_a_new_frame_is_blank(self) -> None:
        frame = Frame()
        assert all(
            frame.cell(row, column) == SPACE
            for row in range(ROWS)
            for column in range(COLUMNS)
        )

    @pytest.mark.parametrize(
        ("row", "column"),
        [(-1, 0), (0, -1), (ROWS, 0), (0, COLUMNS), (ROWS, COLUMNS)],
    )
    def test_positions_outside_the_frame_are_rejected(self, row: int, column: int) -> None:
        frame = Frame()
        with pytest.raises(IndexError):
            frame.cell(row, column)

    @pytest.mark.parametrize(("row", "column"), [(0, 0), (0, 39), (23, 0), (23, 39)])
    def test_the_corners_are_addressable(self, row: int, column: int) -> None:
        assert Frame().cell(row, column) == SPACE


class TestWritingText:
    def test_text_is_placed_from_a_position(self) -> None:
        frame = Frame()
        frame.write(0, 0, "STARDOT")
        assert frame.text_at(0, 0, 7) == "STARDOT"

    def test_text_is_transliterated_and_encoded(self) -> None:
        frame = Frame()
        frame.write(0, 0, "café £5")
        assert frame.text_at(0, 0, 7) == "cafe £5"
        assert frame.cell(0, 5) == 0x23  # the pound sign's G0 position

    def test_writing_past_the_right_edge_is_rejected(self) -> None:
        frame = Frame()
        with pytest.raises(ValueError, match="40 columns"):
            frame.write(0, 35, "TOO LONG")

    def test_text_may_reach_exactly_the_right_edge(self) -> None:
        frame = Frame()
        frame.write(0, 33, "STARDOT")
        assert frame.text_at(0, 33, 7) == "STARDOT"

    def test_writing_does_not_disturb_neighbouring_rows(self) -> None:
        frame = Frame()
        frame.write(5, 0, "X" * COLUMNS)
        assert frame.text_at(4, 0, COLUMNS).strip() == ""
        assert frame.text_at(6, 0, COLUMNS).strip() == ""


class TestAttributes:
    def test_an_attribute_occupies_a_cell(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Control.ALPHA_RED)
        assert frame.cell(0, 0) == Control.ALPHA_RED
        assert frame.is_attribute(0, 0)

    def test_a_character_cell_is_not_an_attribute(self) -> None:
        frame = Frame()
        frame.write(0, 0, "A")
        assert not frame.is_attribute(0, 0)

    def test_a_blank_cell_is_not_an_attribute(self) -> None:
        assert not Frame().is_attribute(0, 0)


class TestSerialisation:
    def test_a_frame_begins_by_clearing_and_homing(self) -> None:
        serialised = Frame().to_bytes()
        assert serialised[:2] == bytes([ScreenControl.CLEAR_SCREEN, ScreenControl.CURSOR_HOME])

    def test_a_blank_frame_is_the_preamble_and_960_spaces(self) -> None:
        serialised = Frame().to_bytes()
        assert serialised == bytes([0x0C, 0x1E]) + b" " * (ROWS * COLUMNS)

    def test_no_line_terminators_are_emitted(self) -> None:
        #  Column 40 wraps of its own accord; a CR or LF would cost a row.
        serialised = Frame().to_bytes()[2:]
        assert bytes([ScreenControl.CARRIAGE_RETURN]) not in serialised
        assert bytes([ScreenControl.LINE_FEED]) not in serialised

    def test_text_appears_in_the_stream(self) -> None:
        frame = Frame()
        frame.write(0, 0, "STARDOT")
        assert frame.to_bytes()[2:9] == b"STARDOT"

    def test_an_attribute_is_escaped(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Control.ALPHA_RED)
        assert frame.to_bytes()[2:4] == b"\x1bA"

    def test_escaping_lengthens_the_stream_without_moving_the_cursor(self) -> None:
        #  The escape costs a second byte on the wire but still one cell on
        #  screen, which is exactly why the grid, not the byte count, is the
        #  authority on layout.
        blank = Frame()
        coloured = Frame()
        coloured.set_attribute(10, 20, Control.ALPHA_CYAN)
        assert len(coloured.to_bytes()) == len(blank.to_bytes()) + 1

    def test_every_byte_is_seven_bit(self) -> None:
        frame = Frame()
        frame.write(0, 0, "£ ½ ¾ ← →")
        frame.set_attribute(1, 0, Control.GRAPHICS_WHITE)
        assert all(byte < 0x80 for byte in frame.to_bytes())


class TestGridRendering:
    """A readable dump, so golden-frame failures diff legibly."""

    def test_a_blank_frame_renders_as_24_blank_rows(self) -> None:
        characters, attributes = Frame().to_grid()
        assert characters == [" " * COLUMNS] * ROWS
        assert attributes == ["." * COLUMNS] * ROWS

    def test_characters_appear_in_the_character_layer(self) -> None:
        frame = Frame()
        frame.write(2, 3, "STARDOT")
        characters, _ = frame.to_grid()
        assert characters[2] == "   STARDOT" + " " * (COLUMNS - 10)

    def test_attributes_appear_in_the_attribute_layer_as_their_escape_letter(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, alpha_colour(Colour.RED))
        characters, attributes = frame.to_grid()
        #  Faithful to the display: an attribute cell shows as a space.
        assert characters[0][0] == " "
        assert attributes[0][0] == "A"

    def test_the_two_layers_are_the_same_shape(self) -> None:
        frame = Frame()
        frame.write(0, 0, "TEXT")
        frame.set_attribute(0, 10, Control.FLASH)
        characters, attributes = frame.to_grid()
        assert len(characters) == len(attributes) == ROWS
        assert all(len(row) == COLUMNS for row in characters + attributes)
