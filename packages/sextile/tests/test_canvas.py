"""Drawing on a frame, where a colour change costs a column.

This is the whole reason colour could not be deferred: an attribute occupies a
character cell, so a row that changes colour twice has thirty-eight columns left
for text, not forty. Canvas does that accounting so callers never have to.

Attributes reset at the start of every row, so each row is written
independently and white text needs no attribute at all.
"""

import pytest

from sextile.viewdata.canvas import DEFAULT_COLOUR, Canvas
from sextile.viewdata.controls import Colour, Control
from sextile.viewdata.frame import COLUMNS


class TestRowDefaults:
    """Pinned against Saa5050::start_of_line() in the Beebium emulation.

    Every row begins white on black with alpha characters and contiguous
    graphics, inheriting nothing from the row above. Canvas is built on that,
    so it is asserted here rather than left as folklore.
    """

    def test_a_row_begins_displaying_white(self) -> None:
        assert DEFAULT_COLOUR is Colour.WHITE

    def test_white_text_therefore_needs_no_attribute(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("PLAIN", DEFAULT_COLOUR)
        assert not canvas.frame.is_attribute(0, 0)


class TestPlainText:
    def test_white_text_costs_only_its_characters(self) -> None:
        canvas = Canvas()
        row = canvas.row(0)
        row.text("STARDOT")
        assert row.column == 7
        assert canvas.frame.text_at(0, 0, 7) == "STARDOT"

    def test_white_needs_no_attribute_because_it_is_the_row_default(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("STARDOT", Colour.WHITE)
        assert canvas.frame.text_at(0, 0, 7) == "STARDOT"
        assert not canvas.frame.is_attribute(0, 0)

    def test_runs_append_to_one_another(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("STAR").text("DOT")
        assert canvas.frame.text_at(0, 0, 7) == "STARDOT"

    def test_transliteration_is_accounted_for_in_the_column(self) -> None:
        #  An ellipsis becomes three characters, so it costs three cells.
        canvas = Canvas()
        row = canvas.row(0)
        row.text("wait…")
        assert row.column == 7
        assert canvas.frame.text_at(0, 0, 7) == "wait..."


class TestColour:
    def test_a_colour_change_places_an_attribute_before_the_text(self) -> None:
        canvas = Canvas()
        row = canvas.row(0)
        row.text("RED", Colour.RED)
        assert canvas.frame.cell(0, 0) == Control.ALPHA_RED
        assert canvas.frame.text_at(0, 1, 3) == "RED"
        assert row.column == 4

    def test_the_same_colour_twice_costs_one_attribute(self) -> None:
        canvas = Canvas()
        row = canvas.row(0)
        row.text("RED", Colour.RED).text("DER", Colour.RED)
        assert row.column == 7
        assert canvas.frame.text_at(0, 1, 6) == "REDDER"

    def test_changing_back_costs_another_attribute(self) -> None:
        canvas = Canvas()
        row = canvas.row(0)
        row.text("RED", Colour.RED).text("WHITE", Colour.WHITE)
        assert canvas.frame.cell(0, 0) == Control.ALPHA_RED
        assert canvas.frame.cell(0, 4) == Control.ALPHA_WHITE
        assert canvas.frame.text_at(0, 5, 5) == "WHITE"
        assert row.column == 10

    def test_black_text_is_refused_rather_than_rendered_invisibly(self) -> None:
        canvas = Canvas()
        with pytest.raises(ValueError, match="black"):
            canvas.row(0).text("INVISIBLE", Colour.BLACK)

    def test_rows_are_independent_because_attributes_reset_each_row(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("RED", Colour.RED)
        second = canvas.row(1)
        second.text("PLAIN", Colour.WHITE)
        #  No attribute needed on row 1: it starts white regardless of row 0.
        assert not canvas.frame.is_attribute(1, 0)
        assert canvas.frame.text_at(1, 0, 5) == "PLAIN"


class TestCapacity:
    def test_a_fresh_row_has_forty_columns(self) -> None:
        assert Canvas().row(0).remaining == COLUMNS

    def test_remaining_falls_by_the_attribute_as_well_as_the_text(self) -> None:
        row = Canvas().row(0)
        row.text("RED", Colour.RED)
        assert row.remaining == COLUMNS - 4

    def test_a_row_may_be_filled_exactly(self) -> None:
        canvas = Canvas()
        row = canvas.row(0)
        row.text("X" * COLUMNS)
        assert row.remaining == 0

    def test_a_coloured_run_may_fill_a_row_exactly(self) -> None:
        canvas = Canvas()
        row = canvas.row(0)
        row.text("X" * (COLUMNS - 1), Colour.CYAN)
        assert row.remaining == 0

    def test_overrunning_a_row_is_refused(self) -> None:
        with pytest.raises(ValueError, match="overruns"):
            Canvas().row(0).text("X" * (COLUMNS + 1))

    def test_the_attribute_counts_towards_the_overrun(self) -> None:
        #  Forty characters fit; forty characters and a colour do not.
        with pytest.raises(ValueError, match="overruns"):
            Canvas().row(0).text("X" * COLUMNS, Colour.CYAN)

    def test_skipping_advances_without_writing(self) -> None:
        canvas = Canvas()
        row = canvas.row(0)
        row.skip(4).text("HERE")
        assert canvas.frame.text_at(0, 0, 8) == "    HERE"


class TestAlignment:
    def test_centred_text(self) -> None:
        canvas = Canvas()
        canvas.centre(0, "STARDOT")
        assert canvas.frame.text_at(0, 0, COLUMNS).strip() == "STARDOT"
        assert canvas.frame.text_at(0, 16, 7) == "STARDOT"

    def test_centred_text_with_colour_keeps_the_text_centred(self) -> None:
        canvas = Canvas()
        canvas.centre(0, "STARDOT", Colour.YELLOW)
        assert canvas.frame.cell(0, 15) == Control.ALPHA_YELLOW
        assert canvas.frame.text_at(0, 16, 7) == "STARDOT"

    def test_centring_full_width_coloured_text_shifts_it_off_the_left_edge(self) -> None:
        #  There is no column to the left of zero for the attribute, so the text
        #  gives up its centring rather than the colour being silently dropped.
        canvas = Canvas()
        canvas.centre(0, "X" * (COLUMNS - 1), Colour.RED)
        assert canvas.frame.cell(0, 0) == Control.ALPHA_RED
        assert canvas.frame.text_at(0, 1, COLUMNS - 1) == "X" * (COLUMNS - 1)

    def test_right_aligned_text(self) -> None:
        canvas = Canvas()
        canvas.right(0, "8202608021")
        assert canvas.frame.text_at(0, COLUMNS - 10, 10) == "8202608021"

    def test_right_aligned_text_with_colour_reserves_the_attribute_cell(self) -> None:
        canvas = Canvas()
        canvas.right(0, "8202608021", Colour.CYAN)
        assert canvas.frame.cell(0, COLUMNS - 11) == Control.ALPHA_CYAN
        assert canvas.frame.text_at(0, COLUMNS - 10, 10) == "8202608021"


class TestParagraphs:
    def test_wrapped_text_fills_consecutive_rows(self) -> None:
        canvas = Canvas()
        canvas.paragraph(0, 3, "the quick brown fox jumps over the lazy dog", width=20)
        assert canvas.frame.text_at(0, 0, 20).strip() == "the quick brown fox"

    def test_paragraphs_report_the_next_free_row(self) -> None:
        canvas = Canvas()
        next_row = canvas.paragraph(0, 10, "one two three", width=10)
        assert next_row == 2

    def test_text_beyond_the_available_rows_is_returned_rather_than_dropped(self) -> None:
        canvas = Canvas()
        _, overflow = canvas.paragraph_with_overflow(0, 1, "one two three four", width=10)
        assert overflow == "three four"

    def test_nothing_overflows_when_it_all_fits(self) -> None:
        canvas = Canvas()
        _, overflow = canvas.paragraph_with_overflow(0, 5, "one two", width=10)
        assert overflow == ""


class TestWritingAfterSomethingElse:
    """A second writer on a row inherits the colour already in force there.

    Attributes reset at the start of a row, not at the start of a write. A
    writer that skips over an earlier colour change and then assumes white
    would emit no attribute, and its text would silently take that colour --
    which is exactly what happened to the page number in the header, showing
    cyan behind the title's attribute rather than white.
    """

    def test_a_later_write_in_white_is_given_its_attribute(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("TITLE", Colour.CYAN)
        canvas.right(0, "1a", Colour.WHITE)
        _, attributes = canvas.frame.to_grid()
        assert "G" in attributes[0], attributes[0]

    def test_the_later_text_is_not_left_in_the_earlier_colour(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("TITLE", Colour.CYAN)
        canvas.right(0, "1a", Colour.WHITE)
        _, attributes = canvas.frame.to_grid()
        assert attributes[0].index("G") > attributes[0].index("F")

    def test_no_attribute_where_the_colour_already_matches(self) -> None:
        #  Still only one attribute cell where one will do.
        canvas = Canvas()
        canvas.row(0).text("TITLE", Colour.CYAN)
        canvas.right(0, "1a", Colour.CYAN)
        _, attributes = canvas.frame.to_grid()
        assert attributes[0].count("F") == 1

    def test_a_graphics_colour_counts_as_the_colour_in_force(self) -> None:
        canvas = Canvas()
        canvas.frame.set_attribute(0, 0, Control.GRAPHICS_RED)
        canvas.right(0, "X", Colour.RED)
        _, attributes = canvas.frame.to_grid()
        assert "A" not in attributes[0]

    def test_skipping_over_nothing_still_starts_white(self) -> None:
        canvas = Canvas()
        canvas.right(0, "1a", Colour.WHITE)
        _, attributes = canvas.frame.to_grid()
        assert attributes[0] == "." * COLUMNS
