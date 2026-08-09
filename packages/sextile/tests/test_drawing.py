"""Free functions for putting things on a frame.

Small operations, each of which had been written out three or four times: the
sort of thing that drifts quietly until two pages disagree about how much room
a heading has.
"""

import pytest

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour, Control
from sextile.viewdata.drawing import SOLID, bar, centred, centred_double, rule
from sextile.viewdata.encoding import cell_count, fitted
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
    def test_a_rule_crosses_the_row_but_for_its_margins(self) -> None:
        #  Two cells at each end: the colour and the separated attribute have
        #  to go somewhere on the left, and the right matches them.
        canvas = Canvas()
        rule(canvas, 1)
        assert rows_of(canvas)[1].count(SOLID) == COLUMNS - 4

    def test_it_is_separated_graphics(self) -> None:
        #  The separated attribute comes before the colour, which is the order
        #  the composition emits for every separated run: the colour attribute
        #  is what enters graphics, and it enters the set already chosen.
        canvas = Canvas()
        rule(canvas, 1)
        assert canvas.frame.cell(1, 0) == Control.SEPARATED_GRAPHICS
        assert canvas.frame.is_attribute(1, 1)

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


def middle_of(canvas: Canvas, row: int) -> float:
    """The middle of what is drawn on a row, in cells, ignoring attributes.

    An attribute displays as a blank, so it is not part of what a reader sees
    to be centred or not.
    """
    lit = [
        column
        for column in range(COLUMNS)
        if not canvas.frame.is_attribute(row, column)
        and canvas.frame.cell(row, column) not in (0x20, 0)
    ]
    return (lit[0] + lit[-1] + 1) / 2 if lit else 0.0


class TestOneMiddleForTheWholeFrame:
    """Everything centred on a frame agrees where the middle is.

    Three things centre themselves here -- text, rules, and lettering made of
    blocks -- and each of them once worked it out for itself. They came out as
    much as a cell and a half apart, which on a title frame is plainly visible:
    the heading sat left of the rule above it.
    """

    @pytest.mark.parametrize("text", ["A", "AB", "ABC", "V I E W D A T A", "X" * 30])
    def test_a_line_of_text_sits_in_the_middle(self, text: str) -> None:
        canvas = Canvas()
        centred(canvas, 0, text)
        assert abs(middle_of(canvas, 0) - COLUMNS / 2) <= 0.5

    @pytest.mark.parametrize("text", ["A", "AB", "ABC", "V I E W D A T A"])
    def test_and_a_colour_does_not_move_it(self, text: str) -> None:
        #  The attribute comes out of the room before the text, so the text
        #  lands where it would have without one. It used to land a cell right.
        plain, coloured = Canvas(), Canvas()
        centred(plain, 0, text)
        centred(coloured, 0, text, Colour.YELLOW)
        assert middle_of(plain, 0) == middle_of(coloured, 0)

    def test_a_rule_leaves_the_same_margin_at_each_end(self) -> None:
        #  A rule cannot begin before its attributes, so the room they take on
        #  the left is left on the right as well rather than being run into.
        canvas = Canvas()
        rule(canvas, 0)
        assert middle_of(canvas, 0) == COLUMNS / 2

    def test_and_a_rule_and_a_heading_share_it(self) -> None:
        canvas = Canvas()
        rule(canvas, 0)
        centred(canvas, 1, "V I E W D A T A", Colour.CYAN)
        assert abs(middle_of(canvas, 0) - middle_of(canvas, 1)) <= 0.5
