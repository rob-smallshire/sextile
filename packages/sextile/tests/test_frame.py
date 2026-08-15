"""A viewdata frame: 24 rows of 40 cells, each holding a character or an attribute.

The geometry is measured, not assumed -- see docs/viewdata-encoding.md. Commstar
wraps from the bottom right cell back to the top left rather than scrolling, so a
frame that emitted even one cell too many would corrupt the top of the frame it
had just drawn. Making the grid fixed-size removes that failure entirely.
"""

import pytest

from sextile.viewdata.controls import Attribute, Colour, alpha_colour
from sextile.viewdata.encoding import ScreenControl, encode_attribute
from sextile.viewdata.frame import COLUMNS, FRAME_PREAMBLE, ROWS, Frame

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
        frame.set_attribute(0, 0, Attribute.ALPHA_RED)
        assert frame.cell(0, 0) == Attribute.ALPHA_RED
        assert frame.is_attribute(0, 0)

    def test_a_character_cell_is_not_an_attribute(self) -> None:
        frame = Frame()
        frame.write(0, 0, "A")
        assert not frame.is_attribute(0, 0)

    def test_a_blank_cell_is_not_an_attribute(self) -> None:
        assert not Frame().is_attribute(0, 0)


class TestSerialisation:
    def test_a_frame_begins_by_hiding_the_cursor_clearing_and_homing(self) -> None:
        assert Frame().to_bytes().startswith(FRAME_PREAMBLE)
        assert bytes([0x14, 0x0C, 0x1E]) == FRAME_PREAMBLE

    def test_the_untrimmed_form_is_the_preamble_and_960_cells(self) -> None:
        serialised = Frame().to_bytes(trim=False)
        assert serialised == FRAME_PREAMBLE + b" " * (ROWS * COLUMNS)

    def test_the_untrimmed_form_emits_no_line_terminators(self) -> None:
        #  Column 40 wraps of its own accord, so walking the cursor by writing
        #  every cell needs no CR or LF at all. See TestTrimming for the form
        #  actually sent.
        serialised = Frame().to_bytes(trim=False)[len(FRAME_PREAMBLE) :]
        assert bytes([ScreenControl.CARRIAGE_RETURN]) not in serialised
        assert bytes([ScreenControl.LINE_FEED]) not in serialised

    def test_text_appears_in_the_stream(self) -> None:
        frame = Frame()
        frame.write(0, 0, "STARDOT")
        assert frame.to_bytes()[len(FRAME_PREAMBLE) :][:7] == b"STARDOT"

    def test_an_attribute_is_escaped(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.ALPHA_RED)
        assert frame.to_bytes()[len(FRAME_PREAMBLE) :][:2] == b"\x1bA"

    def test_escaping_lengthens_the_stream_without_moving_the_cursor(self) -> None:
        #  The escape costs a second byte on the wire but still one cell on
        #  screen, which is exactly why the grid, not the byte count, is the
        #  authority on layout. Compared untrimmed, where every cell is sent.
        blank = Frame()
        coloured = Frame()
        coloured.set_attribute(10, 20, Attribute.ALPHA_CYAN)
        assert len(coloured.to_bytes(trim=False)) == len(blank.to_bytes(trim=False)) + 1

    def test_every_byte_is_seven_bit(self) -> None:
        frame = Frame()
        frame.write(0, 0, "£ ½ ¾ ← →")
        frame.set_attribute(1, 0, Attribute.GRAPHICS_WHITE)
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
        frame.set_attribute(0, 10, Attribute.FLASH)
        characters, attributes = frame.to_grid()
        assert len(characters) == len(attributes) == ROWS
        assert all(len(row) == COLUMNS for row in characters + attributes)


class TestTrimming:
    """Trailing blanks are not sent.

    The frame begins by clearing the screen, so a space at the end of a row
    overwrites nothing: it exists only to walk the cursor forward. A carriage
    return and line feed do that in two bytes instead of up to forty, and both
    were measured putting twenty-four rows on rows 0-23 in the geometry spike.

    Rows that fill all forty columns get no terminator, because column 40 wraps
    of its own accord and a terminator there would skip a row.
    """

    def test_a_blank_frame_is_nothing_but_the_preamble(self) -> None:
        #  The screen has just been cleared; there is nothing left to say.
        assert Frame().to_bytes() == FRAME_PREAMBLE

    def test_a_row_stops_at_its_last_written_cell(self) -> None:
        frame = Frame()
        frame.write(0, 0, "HI")
        assert frame.to_bytes() == FRAME_PREAMBLE + b"HI"

    def test_a_short_row_is_followed_by_a_terminator(self) -> None:
        frame = Frame()
        frame.write(0, 0, "HI")
        frame.write(1, 0, "THERE")
        assert frame.to_bytes() == FRAME_PREAMBLE + b"HI\r\n" + b"THERE"

    def test_a_full_row_needs_no_terminator(self) -> None:
        #  Column 40 wraps by itself; a terminator would skip a row.
        frame = Frame()
        frame.write(0, 0, "X" * COLUMNS)
        frame.write(1, 0, "Y")
        assert frame.to_bytes() == FRAME_PREAMBLE + b"X" * COLUMNS + b"Y"

    def test_a_blank_row_between_two_written_ones_costs_two_bytes(self) -> None:
        frame = Frame()
        frame.write(0, 0, "A")
        frame.write(2, 0, "C")
        assert frame.to_bytes() == FRAME_PREAMBLE + b"A\r\n" + b"\r\n" + b"C"

    def test_nothing_is_sent_after_the_last_written_row(self) -> None:
        frame = Frame()
        frame.write(0, 0, "ONLY")
        assert frame.to_bytes().endswith(b"ONLY")

    def test_a_trailing_attribute_is_kept(self) -> None:
        #  An attribute is not a blank, even where nothing follows it.
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.ALPHA_RED)
        assert frame.to_bytes() == FRAME_PREAMBLE + b"\x1bA"

    def test_the_untrimmed_form_is_still_available(self) -> None:
        #  So that a spike can compare the two on real hardware.
        assert len(Frame().to_bytes(trim=False)) == len(FRAME_PREAMBLE) + ROWS * COLUMNS

    def test_trimming_never_lengthens_a_frame(self) -> None:
        frame = Frame()
        for row in range(ROWS):
            frame.write(row, 0, "X" * COLUMNS)
        assert len(frame.to_bytes()) <= len(frame.to_bytes(trim=False))

    def test_a_wholly_full_frame_is_unchanged_by_trimming(self) -> None:
        frame = Frame()
        for row in range(ROWS):
            frame.write(row, 0, "X" * COLUMNS)
        assert frame.to_bytes() == frame.to_bytes(trim=False)


class TestSendingPartOfARow:
    """A row of a multi-row repaint must stop short of column 40.

    Measured on real Commstar in `docs/spikes/spike_suggestion_block.py`: a row
    written to all forty columns wraps of its own accord, so the cursor is
    already on the next row and a cursor down after it moves down a second one.
    A three-row block written full width lands on rows 4, 6 and 8.
    """

    def test_a_row_is_sent_whole_by_default(self) -> None:
        frame = Frame()
        frame.write(0, 0, "HELLO")
        assert len(frame.row_bytes(0)) == COLUMNS

    def test_or_stopped_where_it_is_told(self) -> None:
        frame = Frame()
        frame.write(0, 0, "HELLO")
        assert frame.row_bytes(0, upto=5) == b"HELLO"

    def test_trimmed_to_what_is_written(self) -> None:
        frame = Frame()
        frame.write(0, 0, "HELLO")
        assert frame.row_bytes(0, upto=frame.used_columns(0)) == b"HELLO"

    def test_a_blank_row_trims_to_nothing(self) -> None:
        assert Frame().row_bytes(0, upto=Frame().used_columns(0)) == b""

    def test_an_attribute_still_travels_escaped(self) -> None:
        #  Trimming changes how much of a row is sent, and nothing about how
        #  what is sent is encoded.
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.ALPHA_YELLOW)
        frame.write(0, 1, "HI")
        sent = frame.row_bytes(0, upto=frame.used_columns(0))
        assert sent == encode_attribute(Attribute.ALPHA_YELLOW) + b"HI"

    def test_the_width_a_row_uses_counts_attributes(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.ALPHA_YELLOW)
        frame.write(0, 1, "HI")
        assert frame.used_columns(0) == 3
