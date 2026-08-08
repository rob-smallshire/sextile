"""Free functions for putting things on a frame.

Small operations, each of which had been written out three or four times: the
sort of thing that drifts quietly until two pages disagree about how much room
a heading has.
"""

import pytest

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour, Control
from sextile.viewdata.drawing import SOLID, bar, centred, centred_double, fitted, rule
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS


def rows_of(canvas: Canvas) -> list[str]:
    characters, _ = canvas.frame.to_grid()
    return characters


class TestFitting:
    def test_text_that_fits_is_untouched(self) -> None:
        assert fitted("STARDOT", 10) == "STARDOT"

    def test_text_that_does_not_is_shortened(self) -> None:
        assert fitted("STARDOT", 4) == "STAR"

    def test_no_room_is_no_text(self) -> None:
        assert fitted("STARDOT", 0) == ""

    def test_it_counts_cells_and_not_characters(self) -> None:
        #  `…` is drawn as three full stops, so it costs three cells.
        assert cell_count(fitted("ab…", 4)) <= 4

    def test_a_character_that_will_not_fit_is_dropped_whole(self) -> None:
        assert fitted("…", 2) == ""


class TestCentring:
    def test_it_puts_text_in_the_middle(self) -> None:
        canvas = Canvas()
        centred(canvas, 0, "AB")
        row = rows_of(canvas)[0]
        assert row.index("AB") == (COLUMNS - 2) // 2

    def test_the_colour_attribute_is_paid_for_before_the_text(self) -> None:
        #  So the text lands where it would have without a colour.
        plain, coloured = Canvas(), Canvas()
        centred(plain, 0, "ABC")
        centred(coloured, 0, "ABC", Colour.YELLOW)
        assert abs(rows_of(plain)[0].index("ABC") - rows_of(coloured)[0].index("ABC")) <= 1

    def test_text_too_wide_is_fitted_rather_than_overrunning(self) -> None:
        canvas = Canvas()
        centred(canvas, 0, "X" * 80, Colour.YELLOW)
        assert len(rows_of(canvas)[0]) == COLUMNS

    def test_it_can_be_centred_in_part_of_a_row(self) -> None:
        canvas = Canvas()
        centred(canvas, 0, "AB", width=10)
        assert rows_of(canvas)[0].index("AB") == 4


class TestCentringAtTwiceTheHeight:
    def test_both_rows_are_written(self) -> None:
        canvas = Canvas()
        centred_double(canvas, 4, "STARDOT", Colour.YELLOW)
        assert rows_of(canvas)[4] == rows_of(canvas)[5]

    def test_and_both_carry_the_attribute(self) -> None:
        canvas = Canvas()
        centred_double(canvas, 4, "STARDOT", Colour.YELLOW)
        for row in (4, 5):
            assert canvas.frame.cell(row, canvas.frame.to_grid()[0][row].index("S") - 2)


class TestRules:
    def test_a_rule_fills_the_row(self) -> None:
        canvas = Canvas()
        rule(canvas, 1)
        assert rows_of(canvas)[1].count(SOLID) == COLUMNS - 2

    def test_it_is_separated_graphics(self) -> None:
        canvas = Canvas()
        rule(canvas, 1)
        assert canvas.frame.cell(1, 1) == Control.SEPARATED_GRAPHICS

    def test_and_takes_a_colour(self) -> None:
        canvas = Canvas()
        rule(canvas, 1, Colour.RED)
        assert canvas.frame.is_attribute(1, 0)


class TestBars:
    def test_a_full_bar_is_solid(self) -> None:
        canvas = Canvas()
        bar(canvas, 0, colour=Colour.YELLOW)
        assert rows_of(canvas)[0].count(SOLID) == COLUMNS - 1

    def test_a_part_bar_is_partly_solid(self) -> None:
        canvas = Canvas()
        bar(canvas, 0, colour=Colour.YELLOW, cells=10, lit=4)
        assert rows_of(canvas)[0].count(SOLID) == 4

    def test_the_unlit_part_is_written_and_not_merely_skipped(self) -> None:
        #  So that a bar drawn over a longer one shortens it.
        canvas = Canvas()
        bar(canvas, 0, colour=Colour.YELLOW, cells=10, lit=10)
        bar(canvas, 0, colour=Colour.YELLOW, cells=10, lit=3)
        assert rows_of(canvas)[0].count(SOLID) == 3

    def test_it_can_begin_part_way_along(self) -> None:
        canvas = Canvas()
        bar(canvas, 0, colour=Colour.YELLOW, column=20, cells=5, lit=5)
        assert rows_of(canvas)[0].index(SOLID) == 21

    def test_more_lit_than_there_is_room_for_is_clamped(self) -> None:
        canvas = Canvas()
        bar(canvas, 0, colour=Colour.YELLOW, cells=5, lit=99)
        assert rows_of(canvas)[0].count(SOLID) == 5

    def test_a_bar_with_no_room_is_refused(self) -> None:
        canvas = Canvas()
        with pytest.raises(ValueError):
            bar(canvas, 0, colour=Colour.YELLOW, column=COLUMNS)
