"""Drawing on a frame, where a colour change costs a column.

This is the whole reason colour could not be deferred: an attribute occupies a
character cell, so a row that changes colour twice has thirty-eight columns left
for text, not forty. Canvas does that accounting so callers never have to.

Attributes reset at the start of every row, so each row is written
independently and white text needs no attribute at all.
"""

import pytest

from sextile.viewdata.canvas import DEFAULT_COLOUR, Canvas, Span
from sextile.viewdata.controls import Attribute, Colour, alpha_colour
from sextile.viewdata.frame import COLUMNS


def rows_of(canvas: Canvas) -> list[str]:
    characters, _ = canvas.frame.to_grid()
    return characters


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

    def test_runs_fill_to_the_row_edge_by_default(self) -> None:
        canvas = Canvas()
        canvas.row(0).runs([Span("X" * COLUMNS, Colour.RED)])
        #  One attribute cell, then the rest of the row.
        assert canvas.frame.text_at(0, 1, COLUMNS - 1) == "X" * (COLUMNS - 1)

    def test_runs_can_be_held_to_a_cells_budget(self) -> None:
        #  With cells=, the runs give way within that budget rather than at the
        #  row edge, so something else can be drawn further along the same row.
        canvas = Canvas()
        canvas.row(0).runs([Span("ABCDEFGHIJ", Colour.RED)], cells=5)
        assert canvas.frame.cell(0, 0) == Attribute.ALPHA_RED
        assert canvas.frame.text_at(0, 1, 4) == "ABCD"
        assert canvas.frame.text_at(0, 5, COLUMNS - 5).strip() == ""

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
        assert canvas.frame.cell(0, 0) == Attribute.ALPHA_RED
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
        assert canvas.frame.cell(0, 0) == Attribute.ALPHA_RED
        assert canvas.frame.cell(0, 4) == Attribute.ALPHA_WHITE
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


class TestStartingAtAColumn:
    """A writer that begins part way along a row someone else has drawn on."""

    def test_it_writes_from_the_column(self) -> None:
        canvas = Canvas()
        canvas.row(0).starting_at(10).text("HERE")
        assert canvas.frame.text_at(0, 10, 4) == "HERE"

    def test_it_reads_the_colour_in_force(self) -> None:
        #  A fresh writer resuming a row someone else coloured takes that
        #  colour, so text in the same colour is not given a needless attribute.
        canvas = Canvas()
        canvas.row(0).text("REDRED", Colour.RED)
        canvas.row(0).starting_at(10).text("SAME", Colour.RED)
        assert canvas.frame.text_at(0, 10, 4) == "SAME"
        assert not canvas.frame.is_attribute(0, 10)

    def test_it_escapes_a_graphics_run_to_its_left(self) -> None:
        #  A fresh writer starting after a mosaic picture is in graphics, so
        #  white text there emits the alpha attribute that returns to letters --
        #  what a legend's words beside a symbol need.
        canvas = Canvas()
        canvas.row(0).mosaic([0b111111] * 3, Colour.YELLOW)
        canvas.row(0).starting_at(4).text("W", Colour.WHITE)
        assert canvas.frame.cell(0, 4) == Attribute.ALPHA_WHITE
        assert canvas.frame.text_at(0, 5, 1) == "W"


class TestAlignment:
    #  Centring is `drawing.centred`, tested there: it goes through a
    #  Composition, which is where the accounting about attributes belongs. Only
    #  right-alignment is the canvas's own.

    def test_right_aligned_text(self) -> None:
        canvas = Canvas()
        canvas.right(0, "8202608021")
        assert canvas.frame.text_at(0, COLUMNS - 10, 10) == "8202608021"

    def test_right_aligned_text_with_colour_reserves_the_attribute_cell(self) -> None:
        canvas = Canvas()
        canvas.right(0, "8202608021", Colour.CYAN)
        assert canvas.frame.cell(0, COLUMNS - 11) == Attribute.ALPHA_CYAN
        assert canvas.frame.text_at(0, COLUMNS - 10, 10) == "8202608021"


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
        canvas.frame.set_attribute(0, 0, Attribute.GRAPHICS_RED)
        canvas.right(0, "X", Colour.RED)
        _, attributes = canvas.frame.to_grid()
        assert "A" not in attributes[0]

    def test_skipping_over_nothing_still_starts_white(self) -> None:
        canvas = Canvas()
        canvas.right(0, "1a", Colour.WHITE)
        _, attributes = canvas.frame.to_grid()
        assert attributes[0] == "." * COLUMNS


class TestMosaicRuns:
    """Mosaics on a row that also carries text.

    A colour attribute switches the character set as well as the colour, so
    entering graphics costs a cell and returning to text costs another. Canvas
    already did that arithmetic for colour; it has to do it for mode too, or a
    row of text after a rule comes out as mosaic rubbish.
    """

    def test_a_run_of_mosaics_is_written(self) -> None:
        canvas = Canvas()
        canvas.row(0).mosaic([0b111111] * 3, Colour.YELLOW)
        assert canvas.frame.cell(0, 1) == 0x7F

    def test_entering_graphics_costs_a_cell(self) -> None:
        canvas = Canvas()
        writer = canvas.row(0)
        writer.mosaic([0b111111], Colour.YELLOW)
        assert writer.column == 2  # the attribute, then the block

    def test_the_attribute_is_a_graphics_colour(self) -> None:
        canvas = Canvas()
        canvas.row(0).mosaic([0b111111], Colour.YELLOW)
        assert canvas.frame.cell(0, 0) == Attribute.GRAPHICS_YELLOW

    def test_staying_in_graphics_costs_nothing_more(self) -> None:
        canvas = Canvas()
        writer = canvas.row(0)
        writer.mosaic([0b111111], Colour.YELLOW)
        writer.mosaic([0b111111], Colour.YELLOW)
        assert writer.column == 3

    def test_changing_the_graphics_colour_costs_a_cell(self) -> None:
        canvas = Canvas()
        writer = canvas.row(0)
        writer.mosaic([0b111111], Colour.YELLOW)
        writer.mosaic([0b111111], Colour.RED)
        assert writer.column == 4

    def test_separated_graphics_cost_a_cell_of_their_own(self) -> None:
        canvas = Canvas()
        writer = canvas.row(0)
        writer.mosaic([0b111111], Colour.BLUE, separated=True)
        assert writer.column == 3
        assert canvas.frame.cell(0, 0) == Attribute.SEPARATED_GRAPHICS

    def test_going_back_to_text_costs_a_cell(self) -> None:
        #  Without this the text would be drawn as mosaics: the colour attribute
        #  chooses the character set as well as the colour.
        canvas = Canvas()
        writer = canvas.row(0)
        writer.mosaic([0b111111], Colour.YELLOW)
        writer.text("AB", Colour.YELLOW)
        assert canvas.frame.cell(0, 2) == Attribute.ALPHA_YELLOW
        assert writer.column == 5

    def test_text_in_the_same_colour_still_pays_to_leave_graphics(self) -> None:
        canvas = Canvas()
        writer = canvas.row(0)
        writer.mosaic([0b111111], Colour.WHITE)
        before = writer.column
        writer.text("A")
        assert writer.column == before + 2

    def test_a_run_that_overruns_the_row_is_refused(self) -> None:
        canvas = Canvas()
        with pytest.raises(ValueError):
            canvas.row(0).mosaic([0b111111] * COLUMNS, Colour.YELLOW)


class TestABackground:
    """Marking out a field, as the command line has always marked its own.

    A reader needs to see where typing goes. It is the only place on a service
    where a background earns its cells.
    """

    def test_what_follows_sits_on_the_colour(self) -> None:
        canvas = Canvas()
        canvas.row(0).background(Colour.BLUE, text=Colour.WHITE).text("TROND")
        assert canvas.frame.text_at(0, 3, 5) == "TROND"

    def test_it_costs_three_cells(self) -> None:
        #  The hardware's arrangement: a background is taken from a foreground,
        #  so the colour is chosen, made the background, and chosen again for
        #  the text.
        row = Canvas().row(0).background(Colour.BLUE, text=Colour.WHITE)
        assert row.column == 3

    def test_the_three_are_the_ones_the_hardware_wants(self) -> None:
        canvas = Canvas()
        canvas.row(0).background(Colour.BLUE, text=Colour.WHITE)
        frame = canvas.frame
        assert frame.cell(0, 0) == alpha_colour(Colour.BLUE)
        assert frame.cell(0, 1) == Attribute.NEW_BACKGROUND
        assert frame.cell(0, 2) == alpha_colour(Colour.WHITE)

    def test_the_text_colour_is_then_in_force(self) -> None:
        #  So writing in it costs no further attribute.
        row = Canvas().row(0).background(Colour.BLUE, text=Colour.WHITE)
        assert row.colour == Colour.WHITE
        row.text("TROND", Colour.WHITE)
        assert row.column == 3 + len("TROND")

    def test_a_row_with_no_room_for_one_says_so(self) -> None:
        row = Canvas().row(0).skip(COLUMNS - 2)
        with pytest.raises(ValueError, match="background"):
            row.background(Colour.BLUE, text=Colour.WHITE)


class TestEndingABackground:
    """A background runs to the end of the row unless something stops it.

    Which is right for a field a reader may fill, and wrong for one of known
    width: a bar six cells wide says there is room for six, and a bar running
    to column 39 says there is room for thirty.
    """

    def test_it_costs_one_cell(self) -> None:
        row = Canvas().row(0).background(Colour.BLUE, text=Colour.WHITE)
        assert row.end_background().column == 4

    def test_the_cell_is_the_one_the_hardware_wants(self) -> None:
        canvas = Canvas()
        canvas.row(0).background(Colour.BLUE, text=Colour.WHITE).text("54.0N").end_background()
        assert canvas.frame.cell(0, 3 + len("54.0N")) == Attribute.BLACK_BACKGROUND

    def test_what_follows_is_written_in_the_same_colour(self) -> None:
        #  Black is taken as a background directly, being the one colour that
        #  needs no foreground chosen first, so nothing else changes.
        row = Canvas().row(0).background(Colour.BLUE, text=Colour.WHITE).end_background()
        assert row.colour == Colour.WHITE

    def test_a_row_with_no_room_left_says_so(self) -> None:
        row = Canvas().row(0).skip(COLUMNS)
        with pytest.raises(ValueError, match="end a background"):
            row.end_background()
