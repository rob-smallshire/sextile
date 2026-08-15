"""Placing several things on a frame and working out the attributes once.

The cases worth pinning are the ones a sequential writer gets wrong: two runs
in the same style paying twice, and a row that cannot fit being found out only
half way through drawing it.
"""

import pytest

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Align, Composition, DoesNotFit, Style
from sextile.viewdata.controls import Attribute, Colour, alpha_colour
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
        assert canvas.frame.cell(0, 0) == Attribute.ALPHA_CYAN

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
        assert canvas.frame.cell(0, 0) == Attribute.GRAPHICS_YELLOW
        assert canvas.frame.cell(0, 1) == 0x7F

    def test_separated_blocks_cost_a_second_cell(self) -> None:
        composition = Composition().blocks(0, 2, [0b111111], Colour.BLUE, separated=True)
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 0) == Attribute.SEPARATED_GRAPHICS
        assert canvas.frame.cell(0, 1) == Attribute.GRAPHICS_BLUE

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
        assert canvas.frame.cell(1, 0) == Attribute.ALPHA_CYAN

    def test_graphics_on_one_row_do_not_carry_either(self) -> None:
        composition = (
            Composition()
            .blocks(0, 1, [0b111111], Colour.YELLOW)
            .blocks(1, 1, [0b111111], Colour.YELLOW)
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(1, 0) == Attribute.GRAPHICS_YELLOW


class TestTheWholeAttributeSet:
    """Everything the SAA5050 can do, and what each costs.

    The point of handing a compositor a style rather than writing controls is
    that the transitions are not uniform: some cost one cell, one costs three,
    and one cannot be undone at all.
    """

    def test_flashing_costs_a_cell(self) -> None:
        canvas = drawn(Composition().text(0, 1, "AB", style=Style(flashing=True)))
        assert canvas.frame.cell(0, 0) == Attribute.FLASH

    def test_and_steadying_costs_another(self) -> None:
        composition = (
            Composition()
            .text(0, 1, "AB", style=Style(flashing=True))
            .text(0, 4, "CD")
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 3) == Attribute.STEADY

    def test_double_height_costs_a_cell(self) -> None:
        canvas = drawn(Composition().text(0, 1, "AB", style=Style(double_height=True)))
        assert canvas.frame.cell(0, 0) == Attribute.DOUBLE_HEIGHT

    def test_and_is_placed_on_the_row_below_as_well(self) -> None:
        #  Which is how the hardware draws the bottom halves, and the thing
        #  everyone gets wrong by leaving that row blank.
        canvas = drawn(Composition().text(0, 1, "AB", style=Style(double_height=True)))
        assert rows_of(canvas)[1] == rows_of(canvas)[0]
        assert canvas.frame.cell(1, 0) == Attribute.DOUBLE_HEIGHT

    def test_a_background_costs_three_cells(self) -> None:
        #  Choose the colour, make it the background, choose the foreground
        #  again. The hardware has no "set background".
        composition = Composition().text(
            0, 3, "AB", style=Style(colour=Colour.WHITE, background=Colour.BLUE)
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 0) == Attribute.ALPHA_BLUE
        assert canvas.frame.cell(0, 1) == Attribute.NEW_BACKGROUND
        assert canvas.frame.cell(0, 2) == Attribute.ALPHA_WHITE

    def test_a_background_matching_the_foreground_costs_two(self) -> None:
        #  Nothing to change back to, so the third cell is not spent.
        composition = Composition().text(
            0, 2, "AB", style=Style(colour=Colour.BLUE, background=Colour.BLUE)
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 0) == Attribute.ALPHA_BLUE
        assert canvas.frame.cell(0, 1) == Attribute.NEW_BACKGROUND

    def test_going_back_to_black_costs_one(self) -> None:
        composition = (
            Composition()
            .text(0, 3, "AB", style=Style(background=Colour.BLUE))
            .text(0, 6, "CD")
        )
        canvas = drawn(composition)
        assert canvas.frame.cell(0, 5) == Attribute.BLACK_BACKGROUND

    def test_holding_graphics_costs_a_cell(self) -> None:
        composition = Composition().blocks(
            0, 2, [0b111111], style=Style(colour=Colour.RED, hold_graphics=True)
        )
        canvas = drawn(composition)
        assert Attribute.HOLD_GRAPHICS in [canvas.frame.cell(0, c) for c in (0, 1)]

    def test_concealing_costs_a_cell(self) -> None:
        canvas = drawn(Composition().text(0, 1, "AB", style=Style(concealed=True)))
        assert canvas.frame.cell(0, 0) == Attribute.CONCEAL

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


class TestWhereAThingGoesIsTheCompositionsBusiness:
    """Centring is accounting about attributes, so it belongs here.

    A caller that centres by arithmetic of its own has to know what its style
    will cost in cells before it can know where the middle is -- and that is
    exactly what a composition works out. Three of them did, and came out a
    cell and a half apart.
    """

    def test_text_can_ask_for_the_middle_rather_than_a_column(self) -> None:
        layout = Composition().text(0, Align.CENTRE, "ABCD")
        assert layout.runs[0][0].column == (COLUMNS - 4) // 2

    def test_and_lands_in_the_same_cells_when_it_has_a_colour(self) -> None:
        #  The attribute comes out of the room before it, not out of its own.
        plain = Composition().text(0, Align.CENTRE, "ABCD")
        coloured = Composition().text(0, Align.CENTRE, "ABCD", Colour.YELLOW)
        assert plain.runs[0][0].column == coloured.runs[0][0].column

    def test_something_too_wide_to_centre_gives_its_attributes_room(self) -> None:
        #  Centring would put this at column zero, where the attribute has to
        #  go. It is moved along rather than being refused.
        layout = Composition().blocks(0, Align.CENTRE, [0x3F] * (COLUMNS - 1), Colour.RED)
        assert layout.runs[0][0].column == 1

    def test_left_is_as_far_left_as_the_attributes_allow(self) -> None:
        layout = Composition().blocks(0, Align.LEFT, [0x3F] * 4, Colour.RED)
        assert layout.runs[0][0].column == 1

    def test_and_left_is_column_zero_when_nothing_is_needed(self) -> None:
        layout = Composition().text(0, Align.LEFT, "ABCD")
        assert layout.runs[0][0].column == 0

    def test_right_is_flush_with_the_last_column(self) -> None:
        layout = Composition().text(0, Align.RIGHT, "ABCD")
        assert layout.runs[0][0].end == COLUMNS


class TestAPictureIsPlacedAsOneThing:
    """Several rows of blocks that belong together, and are centred together.

    Row by row would let the rows disagree: each would measure its own ink and
    some would take the half-cell shift and others not, and the picture would
    shear.
    """

    def test_its_rows_go_on_consecutive_rows_of_the_frame(self) -> None:
        layout = Composition().picture(3, 10, [[0x3F], [0x3F], [0x3F]])
        assert sorted(layout.runs) == [3, 4, 5]

    def test_and_all_of_them_in_the_same_column(self) -> None:
        #  Rows of different ink, one of which would shift on its own.
        layout = Composition().picture(0, Align.CENTRE, [[0b000001], [0b101010]])
        assert {run.column for runs in layout.runs.values() for run in runs} == {19}

    def test_it_is_centred_on_its_ink_and_not_on_its_cells(self) -> None:
        #  Two cells, with the one block of ink in the second of them. Centring
        #  the cells would put the run at column 19 and the ink off to the
        #  right of the middle; centring the ink puts the run at 18.
        layout = Composition().picture(0, Align.CENTRE, [[0b000000, 0b000001]])
        assert layout.runs[0][0].column == 18

    def test_and_takes_a_blank_block_before_it_where_that_is_nearer(self) -> None:
        #  An odd number of blocks of margin: the ink starts half way into a
        #  cell, which costs nothing, a blank block and an attribute cell
        #  looking the same on the screen.
        layout = Composition().picture(0, Align.CENTRE, [[0b111111] * 19])
        run = layout.runs[0][0]
        assert not run.patterns[0] & 0b010101
        assert run.patterns[0] & 0b101010

    def test_a_column_given_is_still_a_column(self) -> None:
        layout = Composition().picture(0, 7, [[0b000001, 0b000000]])
        assert layout.runs[0][0].patterns == (0b000001, 0b000000)
        assert layout.runs[0][0].column == 7


class TestPanels:
    """A coloured rectangle, with things drawn on top of it.

    The Ceefax pages this is for put a word of mosaic lettering in a coloured
    box: cyan on blue, red on yellow, blue on green. The hardware has no "set
    background" -- only "make the current foreground the background" -- so a
    box costs two cells before anything can be drawn in it, and where those
    cells go decides where the box appears to start. That is arithmetic about
    attributes, so it belongs here rather than in whatever wants a box.
    """

    def test_a_panel_begins_where_it_was_asked_to(self) -> None:
        #  Measured from Beebium: the background is set *at* the attribute
        #  cell, not after it, so the cell carrying NEW_BACKGROUND is already
        #  coloured and is the box's first cell.
        canvas = Canvas()
        layout = Composition()
        layout.panel(0, 10, width=8, colour=Colour.BLUE)
        layout.draw(canvas)
        assert canvas.frame.cell(0, 10) == Attribute.NEW_BACKGROUND

    def test_and_the_cell_before_it_is_what_chooses_the_colour(self) -> None:
        #  Which is still black: a colour attribute cannot colour itself.
        canvas = Canvas()
        layout = Composition()
        layout.panel(0, 10, width=8, colour=Colour.BLUE)
        layout.draw(canvas)
        assert canvas.frame.cell(0, 9) == alpha_colour(Colour.BLUE)

    def test_a_panel_that_ends_before_the_row_does_is_closed(self) -> None:
        #  Or the colour would run to the end of the row, which is what a
        #  background does if nothing stops it.
        canvas = Canvas()
        layout = Composition()
        layout.panel(0, 10, width=8, colour=Colour.BLUE)
        layout.draw(canvas)
        assert canvas.frame.cell(0, 18) == Attribute.BLACK_BACKGROUND

    def test_and_one_that_reaches_the_end_of_the_row_is_not(self) -> None:
        canvas = Canvas()
        layout = Composition()
        layout.panel(0, 10, width=COLUMNS - 10, colour=Colour.BLUE)
        layout.draw(canvas)
        assert not canvas.frame.is_attribute(0, COLUMNS - 1)

    def test_a_panel_can_be_several_rows_deep(self) -> None:
        canvas = Canvas()
        layout = Composition()
        layout.panel(2, 10, width=8, colour=Colour.BLUE, rows=3)
        layout.draw(canvas)
        for row in (2, 3, 4):
            assert canvas.frame.cell(row, 10) == Attribute.NEW_BACKGROUND

    def test_a_panel_with_no_room_for_its_attributes_is_refused(self) -> None:
        layout = Composition()
        layout.panel(0, 0, width=8, colour=Colour.BLUE)
        with pytest.raises(DoesNotFit):
            layout.draw(Canvas())

    def test_it_can_be_asked_for_a_side_of_the_frame(self) -> None:
        layout = Composition()
        panel = layout.panel(0, Align.RIGHT, width=8, colour=Colour.BLUE)
        assert panel.end == COLUMNS


class TestWhatIsDrawnOnAPanel:
    def test_a_run_inside_one_keeps_its_background(self) -> None:
        #  The run says nothing about a background, so it takes the panel's:
        #  otherwise it would turn the box off in the middle of itself.
        canvas = Canvas()
        layout = Composition()
        panel = layout.panel(0, 10, width=12, colour=Colour.BLUE)
        layout.text(0, 13, "NEWS", Colour.CYAN, within=panel).draw(canvas)
        assert canvas.frame.cell(0, 22) == Attribute.BLACK_BACKGROUND
        assert not any(
            canvas.frame.cell(0, column) == Attribute.BLACK_BACKGROUND
            for column in range(11, 22)
        )

    def test_and_pays_for_its_own_colour_and_nothing_else(self) -> None:
        canvas = Canvas()
        layout = Composition()
        panel = layout.panel(0, 10, width=12, colour=Colour.BLUE)
        layout.text(0, 13, "NEWS", Colour.CYAN, within=panel).draw(canvas)
        assert canvas.frame.cell(0, 12) == alpha_colour(Colour.CYAN)

    def test_a_run_outside_one_is_left_alone(self) -> None:
        canvas = Canvas()
        layout = Composition()
        layout.panel(0, 20, width=20, colour=Colour.BLUE)
        layout.text(0, 0, "plain", Colour.WHITE).draw(canvas)
        assert canvas.frame.cell(0, 5) == 0x20

    def test_something_centred_within_a_panel_is_centred_in_the_panel(self) -> None:
        layout = Composition()
        panel = layout.panel(0, 20, width=20, colour=Colour.BLUE)
        layout.text(0, Align.CENTRE, "ABCD", Colour.CYAN, within=panel)
        assert layout.runs[0][-1].column == 20 + (20 - 4) // 2

    def test_and_a_picture_within_one_is_centred_on_its_ink(self) -> None:
        layout = Composition()
        panel = layout.panel(0, 20, width=20, colour=Colour.CYAN)
        layout.picture(0, Align.CENTRE, [[0b111111] * 8], Colour.BLUE, within=panel)
        assert layout.runs[0][-1].column == 20 + (20 - 8) // 2

    def test_a_run_may_still_have_a_background_of_its_own(self) -> None:
        #  A box within a box: the inner one says what it wants and gets it.
        canvas = Canvas()
        layout = Composition()
        panel = layout.panel(0, 10, width=20, colour=Colour.BLUE)
        layout.text(
            0, 16, "X", within=panel, style=Style(colour=Colour.WHITE, background=Colour.RED)
        ).draw(canvas)
        #  Three cells: choose red, make it the background, choose white back.
        assert canvas.frame.cell(0, 13) == alpha_colour(Colour.RED)
        assert canvas.frame.cell(0, 14) == Attribute.NEW_BACKGROUND


class TestUpAndDownAsWellAsAlongTheRow:
    """A picture can be centred in a panel's rows as well as in its columns.

    Finer than a row, too: a cell is three blocks deep, so a line of lettering
    seven blocks tall sits in a box three rows deep with a block above it and a
    block below rather than two blocks under it.
    """

    def test_a_picture_can_ask_for_the_middle_of_a_panel(self) -> None:
        layout = Composition()
        panel = layout.panel(4, 10, width=20, colour=Colour.BLUE, rows=5)
        layout.picture(Align.CENTRE, 12, [[0b111111]] * 3, within=panel)
        assert sorted(layout.runs) == [5, 6, 7]

    def test_and_is_lowered_by_a_block_where_that_is_nearer(self) -> None:
        #  Seven blocks of ink in a box nine deep: a block above and below.
        layout = Composition()
        panel = layout.panel(0, 10, width=20, colour=Colour.BLUE, rows=3)
        #  Two full rows of blocks and one block row more: seven of nine.
        layout.picture(
            Align.CENTRE, 12, [[0b111111], [0b111111], [0b000011]], within=panel
        )
        assert sorted(layout.runs) == [0, 1, 2]
        assert layout.runs[0][0].patterns[0] == 0b111100

    def test_the_middle_of_the_frame_when_there_is_no_panel(self) -> None:
        layout = Composition()
        layout.picture(Align.CENTRE, 12, [[0b111111]] * 4)
        assert sorted(layout.runs) == [10, 11, 12, 13]

    def test_a_row_given_is_still_a_row(self) -> None:
        layout = Composition()
        layout.picture(9, 12, [[0b111111]])
        assert sorted(layout.runs) == [9]


class TestAPanelFittedRoundWhatIsThere:
    """A stripe behind something, without either being told where the other is.

    The thing is placed, then the stripe is fitted to it. Fitted to what it
    lights rather than to the cells it occupies, or the colour comes out a cell
    longer on one side than the other -- which is what it did.
    """

    def test_it_takes_the_cells_the_lettering_lights(self) -> None:
        layout = Composition()
        layout.picture(0, 10, [[0b000000, 0b111111, 0b111111, 0b000000]])
        panel = layout.panel(0, colour=Colour.BLUE, around=[0], padding=3)
        #  The lit cells are 11 and 12; three cells of colour either side.
        assert (panel.column, panel.end) == (8, 16)

    def test_the_same_either_side_even_of_a_half_lit_cell(self) -> None:
        #  The picture begins in the right-hand half of its first cell, as a
        #  centred one often does. What is seen is the cell, so the stripe
        #  reaches the same distance past it at both ends.
        layout = Composition()
        layout.picture(0, 10, [[0b101010, 0b111111]])
        panel = layout.panel(0, colour=Colour.BLUE, around=[0], padding=2)
        assert (panel.column, panel.end) == (8, 14)

    def test_it_still_covers_the_runs_it_is_behind(self) -> None:
        #  Even with no padding at all: a panel stopping short of a run it is
        #  behind would leave that run turning the background off mid-stripe.
        layout = Composition()
        layout.picture(0, 10, [[0b000000, 0b111111, 0b000000]])
        panel = layout.panel(0, colour=Colour.BLUE, around=[0], padding=0)
        assert panel.column <= 10 and panel.end >= 13

    def test_it_can_be_fitted_to_rows_it_does_not_cover(self) -> None:
        #  Which is the point: three rows of lettering, one row of stripe.
        layout = Composition()
        layout.picture(4, 10, [[0b111111]] * 3)
        panel = layout.panel(5, colour=Colour.BLUE, around=[4, 5, 6], padding=1)
        assert panel.rows == (5,)
        assert panel.width == len([0b111111]) + 2

    def test_with_nothing_there_it_says_so(self) -> None:
        with pytest.raises(DoesNotFit, match="nothing on row"):
            Composition().panel(5, colour=Colour.BLUE, around=[4, 5, 6])

    def test_a_panel_is_given_one_thing_or_the_other(self) -> None:
        with pytest.raises(DoesNotFit, match="either"):
            Composition().panel(0, colour=Colour.BLUE)
        with pytest.raises(DoesNotFit, match="either"):
            Composition().panel(0, colour=Colour.BLUE, width=4, around=[0])


class TestClosingAPanel:
    def test_costs_one_cell_and_it_is_outside_the_panel(self) -> None:
        #  A second cell would land inside, and take a cell of colour off the
        #  right-hand end -- which is where nobody looks for a missing cell.
        canvas = Canvas()
        layout = Composition()
        panel = layout.panel(0, 10, width=8, colour=Colour.BLUE)
        layout.blocks(0, 12, [0b111111] * 4, Colour.YELLOW, within=panel)
        layout.draw(canvas)
        assert canvas.frame.cell(0, panel.end) == Attribute.BLACK_BACKGROUND
        assert not canvas.frame.is_attribute(0, panel.end - 1)

    def test_and_leaves_the_row_in_the_charset_it_was_in(self) -> None:
        #  Blocks after a panel, in the same colour, cost nothing: the panel
        #  ending is not a reason to leave graphics and come back.
        canvas = Canvas()
        layout = Composition()
        panel = layout.panel(0, 4, width=6, colour=Colour.BLUE)
        layout.blocks(0, 6, [0b111111] * 3, Colour.YELLOW, within=panel)
        layout.blocks(0, 12, [0b111111] * 3, Colour.YELLOW)
        layout.draw(canvas)
        assert [
            column for column in range(COLUMNS) if canvas.frame.is_attribute(0, column)
        ] == [3, 4, 5, 10]
