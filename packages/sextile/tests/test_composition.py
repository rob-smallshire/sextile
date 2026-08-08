"""Placing several things on a frame and working out the attributes once.

The cases worth pinning are the ones a sequential writer gets wrong: two runs
in the same style paying twice, and a row that cannot fit being found out only
half way through drawing it.
"""

import pytest

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Composition, DoesNotFit, Style
from sextile.viewdata.controls import Colour, Control
from sextile.viewdata.frame import COLUMNS


def drawn(composition: Composition) -> Canvas:
    canvas = Canvas()
    composition.draw(canvas)
    return canvas


def rows_of(canvas: Canvas) -> list[str]:
    characters, _ = canvas.frame.to_grid()
    return characters


class TestPlacingText:
    def test_white_text_costs_no_attribute(self) -> None:
        #  Every row opens white, so the commonest case is free.
        canvas = drawn(Composition().text(0, 0, "STARDOT"))
        assert rows_of(canvas)[0].startswith("STARDOT")

    def test_a_colour_costs_a_cell_before_it(self) -> None:
        canvas = drawn(Composition().text(0, 1, "AB", Colour.CYAN))
        assert canvas.frame.cell(0, 0) == Control.ALPHA_CYAN

    def test_text_at_column_zero_in_a_colour_will_not_fit(self) -> None:
        #  There is nowhere to put the attribute.
        assert not Composition().text(0, 0, "AB", Colour.CYAN).fits()

    def test_two_runs_in_one_colour_pay_once(self) -> None:
        composition = Composition().text(0, 1, "AB", Colour.CYAN).text(0, 10, "CD", Colour.CYAN)
        canvas = drawn(composition)
        attributes = [c for c in range(COLUMNS) if canvas.frame.is_attribute(0, c)]
        assert attributes == [0]


class TestPlacingBlocks:
    def test_a_run_of_blocks_enters_graphics(self) -> None:
        canvas = drawn(Composition().blocks(0, 1, [0b111111], Colour.YELLOW))
        assert canvas.frame.cell(0, 0) == Control.GRAPHICS_YELLOW
        assert canvas.frame.cell(0, 1) == 0x7F

    def test_separated_blocks_cost_a_second_cell(self) -> None:
        composition = Composition().blocks(0, 2, [0b111111], Colour.BLUE, separated=True)
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 0) == Control.SEPARATED_GRAPHICS
        assert canvas.frame.cell(0, 1) == Control.GRAPHICS_BLUE

    def test_two_block_runs_in_one_colour_enter_graphics_once(self) -> None:
        #  The case the sequential writer cannot see: nothing between them wants
        #  alpha, so nothing returns to it.
        composition = (
            Composition()
            .blocks(0, 1, [0b111111] * 3, Colour.YELLOW)
            .blocks(0, 30, [0b111111] * 3, Colour.YELLOW)
        )
        canvas = drawn(composition)
        attributes = [c for c in range(COLUMNS) if canvas.frame.is_attribute(0, c)]
        assert attributes == [0]

    def test_text_between_them_makes_it_three(self) -> None:
        #  Leaving graphics and coming back is what costs, and here it is asked
        #  for rather than assumed.
        composition = (
            Composition()
            .blocks(0, 1, [0b111111], Colour.YELLOW)
            .text(0, 5, "AB", Colour.WHITE)
            .blocks(0, 10, [0b111111], Colour.YELLOW)
        )
        canvas = drawn(composition)
        attributes = [c for c in range(COLUMNS) if canvas.frame.is_attribute(0, c)]
        assert len(attributes) == 3


class TestSayingItWillNotFit:
    def test_a_gap_too_small_for_the_attributes(self) -> None:
        composition = Composition().text(0, 0, "AB").blocks(0, 2, [0b111111], Colour.RED)
        assert not composition.fits()
        assert "attribute cell" in composition.problems()[0]

    def test_the_row_and_column_are_named(self) -> None:
        composition = Composition().text(3, 0, "AB").blocks(3, 2, [0b111111], Colour.RED)
        assert "row 3" in composition.problems()[0]
        assert "column 2" in composition.problems()[0]

    def test_overlapping_runs_are_refused(self) -> None:
        composition = Composition().text(0, 0, "ABCDE").text(0, 2, "XY")
        assert "overlaps" in composition.problems()[0]

    def test_a_run_past_the_edge_is_refused_at_once(self) -> None:
        with pytest.raises(DoesNotFit):
            Composition().text(0, 38, "ABCDE")

    def test_drawing_something_that_will_not_fit_raises(self) -> None:
        composition = Composition().text(0, 0, "AB").blocks(0, 2, [0b111111], Colour.RED)
        with pytest.raises(DoesNotFit):
            composition.draw(Canvas())

    def test_and_draws_nothing_at_all(self) -> None:
        #  Planned in full before a cell is written, so a bad row does not leave
        #  half a frame on somebody's screen.
        canvas = Canvas()
        composition = (
            Composition().text(0, 0, "FINE").text(5, 0, "AB").blocks(5, 2, [1], Colour.RED)
        )
        with pytest.raises(DoesNotFit):
            composition.draw(canvas)
        assert rows_of(canvas)[0].strip() == ""


class TestRowsAreIndependent:
    def test_a_colour_on_one_row_does_not_carry_to_the_next(self) -> None:
        composition = Composition().text(0, 1, "AB", Colour.CYAN).text(1, 1, "CD", Colour.CYAN)
        canvas = drawn(composition)
        assert canvas.frame.cell(1, 0) == Control.ALPHA_CYAN

    def test_graphics_on_one_row_do_not_carry_either(self) -> None:
        composition = (
            Composition()
            .blocks(0, 1, [0b111111], Colour.YELLOW)
            .blocks(1, 1, [0b111111], Colour.YELLOW)
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(1, 0) == Control.GRAPHICS_YELLOW


class TestTheWholeAttributeSet:
    """Everything the SAA5050 can do, and what each costs.

    The point of handing a compositor a style rather than writing controls is
    that the transitions are not uniform: some cost one cell, one costs three,
    and one cannot be undone at all.
    """

    def test_flashing_costs_a_cell(self) -> None:
        canvas = drawn(Composition().text(0, 1, "AB", style=Style(flashing=True)))
        assert canvas.frame.cell(0, 0) == Control.FLASH

    def test_and_steadying_costs_another(self) -> None:
        composition = (
            Composition()
            .text(0, 1, "AB", style=Style(flashing=True))
            .text(0, 4, "CD")
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 3) == Control.STEADY

    def test_double_height_costs_a_cell(self) -> None:
        canvas = drawn(Composition().text(0, 1, "AB", style=Style(double_height=True)))
        assert canvas.frame.cell(0, 0) == Control.DOUBLE_HEIGHT

    def test_and_is_placed_on_the_row_below_as_well(self) -> None:
        #  Which is how the hardware draws the bottom halves, and the thing
        #  everyone gets wrong by leaving that row blank.
        canvas = drawn(Composition().text(0, 1, "AB", style=Style(double_height=True)))
        assert rows_of(canvas)[1] == rows_of(canvas)[0]
        assert canvas.frame.cell(1, 0) == Control.DOUBLE_HEIGHT

    def test_a_background_costs_three_cells(self) -> None:
        #  Choose the colour, make it the background, choose the foreground
        #  again. The hardware has no "set background".
        composition = Composition().text(
            0, 3, "AB", style=Style(colour=Colour.WHITE, background=Colour.BLUE)
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 0) == Control.ALPHA_BLUE
        assert canvas.frame.cell(0, 1) == Control.NEW_BACKGROUND
        assert canvas.frame.cell(0, 2) == Control.ALPHA_WHITE

    def test_a_background_matching_the_foreground_costs_two(self) -> None:
        #  Nothing to change back to, so the third cell is not spent.
        composition = Composition().text(
            0, 2, "AB", style=Style(colour=Colour.BLUE, background=Colour.BLUE)
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 0) == Control.ALPHA_BLUE
        assert canvas.frame.cell(0, 1) == Control.NEW_BACKGROUND

    def test_going_back_to_black_costs_one(self) -> None:
        composition = (
            Composition()
            .text(0, 3, "AB", style=Style(background=Colour.BLUE))
            .text(0, 6, "CD")
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 5) == Control.BLACK_BACKGROUND

    def test_holding_graphics_costs_a_cell(self) -> None:
        composition = Composition().blocks(
            0, 2, [0b111111], style=Style(colour=Colour.RED, held=True)
        )
        canvas = drawn(composition)
        assert Control.HOLD_GRAPHICS in [canvas.frame.cell(0, c) for c in (0, 1)]

    def test_concealing_costs_a_cell(self) -> None:
        canvas = drawn(Composition().text(0, 1, "AB", style=Style(concealed=True)))
        assert canvas.frame.cell(0, 0) == Control.CONCEAL

    def test_and_cannot_be_undone_within_a_row(self) -> None:
        #  The hardware clears it at the end of a row and nowhere else, so a
        #  composition asking for that is refused rather than drawn wrongly.
        composition = (
            Composition().text(0, 1, "AB", style=Style(concealed=True)).text(0, 5, "CD")
        )
        assert "conceal cannot be turned off" in composition.problems()[0]

    def test_a_style_reached_in_one_go_is_reached_in_one_pass(self) -> None:
        #  Flashing double-height cyan on blue: three for the background, one
        #  for the flash, one for the height.
        style = Style(
            colour=Colour.CYAN,
            background=Colour.BLUE,
            flashing=True,
            double_height=True,
        )
        canvas = drawn(Composition().text(0, 5, "AB", style=style))
        attributes = [c for c in range(5) if canvas.frame.is_attribute(0, c)]
        assert len(attributes) == 5
