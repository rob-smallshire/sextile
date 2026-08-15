"""Setting text in a mosaic font: the three spacings, and what they measure."""

import pytest
from test_drawing import middle_of as middle_of_row

from sextile.viewdata import lettering
from sextile.viewdata.blocks import BLOCKS_ACROSS, BLOCKS_DOWN
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Align, Composition, DoesNotFit
from sextile.viewdata.controls import Attribute, Colour
from sextile.viewdata.drawing import rule
from sextile.viewdata.font import font_names, load_font, read_font
from sextile.viewdata.frame import COLUMNS, ROWS, Frame
from sextile.viewdata.lettering import Spacing

#  A face with three letters of known width, so that the arithmetic of each
#  spacing can be checked by hand rather than against a real font's accidents.
#
#  I is one block of ink, sitting one block in from the left of a four-block
#  design width. L has ink low down on the right, T high up on the right: the
#  pair that kerning exists for.
TOY = read_font("""\
name: Toy
height: 3
fixed: 4

glyph u+0020 advance 2

glyph u+0049 advance 2 bearing 1  I
#
#
#

glyph u+004c advance 4  L
#..
#..
###

glyph u+0054 advance 4  T
###
.#.
.#.
""")


def drawn(bitmap: list[list[bool]]) -> list[str]:
    return ["".join("#" if block else "." for block in row) for row in bitmap]


class TestFixedSpacing:
    def test_every_letter_takes_the_design_width(self) -> None:
        #  Four blocks each, less the blank the second one ends with.
        assert lettering.width("II", TOY, spacing=Spacing.FIXED) == 6

    def test_and_sits_where_the_designer_put_it_within_that(self) -> None:
        #  Without the bearing every letter would jam against the left of its
        #  cell, which is the one thing fixed setting must not do.
        assert drawn(lettering.bitmap("II", TOY, spacing=Spacing.FIXED)) == [
            ".#...#",
            ".#...#",
            ".#...#",
        ]

    def test_a_space_takes_the_design_width_like_anything_else(self) -> None:
        assert lettering.width("I I", TOY, spacing=Spacing.FIXED) == 10


class TestProportionalSpacing:
    def test_every_letter_takes_its_own_advance(self) -> None:
        assert lettering.width("II", TOY, spacing=Spacing.PROPORTIONAL) == 3

    def test_and_the_bearing_is_left_behind(self) -> None:
        assert drawn(lettering.bitmap("II", TOY, spacing=Spacing.PROPORTIONAL)) == [
            "#.#",
            "#.#",
            "#.#",
        ]

    def test_a_space_takes_the_width_the_font_gives_it(self) -> None:
        assert lettering.width("I I", TOY, spacing=Spacing.PROPORTIONAL) == 5

    def test_it_is_what_a_page_gets_if_it_says_nothing(self) -> None:
        assert lettering.width("II", TOY) == 3


class TestKerning:
    def test_letters_that_cannot_close_up_are_set_as_they_were(self) -> None:
        assert lettering.width("II", TOY, spacing=Spacing.KERNED) == 3

    def test_a_pair_that_leaves_room_is_closed_up(self) -> None:
        #  T's arm is high and L's foot is low, so the two may overlap by a
        #  block without either touching the other on any row.
        assert lettering.width("LT", TOY, spacing=Spacing.KERNED) == 6

    def test_and_the_ink_lands_where_the_measurement_said_it_would(self) -> None:
        assert drawn(lettering.bitmap("LT", TOY, spacing=Spacing.KERNED)) == [
            "#..###",
            "#...#.",
            "###.#.",
        ]

    def test_a_pair_that_would_touch_is_left_where_it_was(self) -> None:
        #  The same two letters the other way round: T's arm is at the height
        #  L's stem is, so there is nothing to be had and nothing is taken.
        assert lettering.width("TL", TOY, spacing=Spacing.KERNED) == 7
        assert lettering.width("TL", TOY, spacing=Spacing.PROPORTIONAL) == 7

    def test_no_pair_may_close_up_by_more_than_it_is_allowed(self) -> None:
        #  Otherwise a narrow letter after a space slides back over the space,
        #  and the words run together.
        assert lettering.width("L T", TOY, spacing=Spacing.KERNED, limit=1) == 9

    def test_a_letter_is_never_pushed_into_the_one_before_it(self) -> None:
        wide = read_font(
            "name: W\nheight: 1\nfixed: 2\n\nglyph u+0041 advance 1  A\n##\n"
        )
        #  A's advance is less than its own ink, so proportional setting would
        #  have the two overlap. Kerning has to push it out, not pull it in.
        assert lettering.width("AA", wide, spacing=Spacing.KERNED) == 5

    def test_the_gap_it_keeps_between_letters_can_be_widened(self) -> None:
        assert lettering.width("LT", TOY, spacing=Spacing.KERNED, gap=2) == 7


class TestTrimmingWhatIsNotDrawn:
    def test_a_line_is_only_as_tall_as_its_own_ink(self) -> None:
        #  A face leaves room for descenders and accents whether the line uses
        #  them or not, and three blank block-rows is a whole row of a screen
        #  that has twenty-four. STARDOT in silkscreen is five blocks of ink
        #  in a nine-block face.
        assert len(lettering.bitmap("STARDOT", load_font("silkscreen"))) == 5
        assert len(lettering.cells("STARDOT", load_font("silkscreen"))) == 2

    def test_and_a_line_that_uses_them_keeps_them(self) -> None:
        #  Silkscreen's lowercase are small capitals with nothing below the
        #  line, so this needs a face that has descenders to say anything.
        acorn = load_font("acorn")
        assert len(lettering.bitmap("Stardot pg", acorn)) > len(
            lettering.bitmap("STARDOT", acorn)
        )

    def test_the_face_can_be_kept_at_its_full_height_instead(self) -> None:
        #  Two lines set separately only sit on the same baseline if neither
        #  is trimmed, so this is how a page asks for that.
        silkscreen = load_font("silkscreen")
        assert len(lettering.bitmap("STARDOT", silkscreen, trim=False)) == silkscreen.height

    def test_nothing_at_all_still_has_the_height_of_the_face(self) -> None:
        assert len(lettering.bitmap("", TOY)) == TOY.height


class TestWhatIsSet:
    def test_the_lettering_is_as_tall_as_the_ink(self) -> None:
        assert len(lettering.bitmap("I", TOY)) == TOY.height

    def test_nothing_at_all_is_a_bitmap_of_no_width(self) -> None:
        assert lettering.width("", TOY) == 0
        assert drawn(lettering.bitmap("", TOY)) == ["", "", ""]

    def test_a_character_the_face_has_no_glyph_for_is_substituted(self) -> None:
        #  As transliteration does; a banner with a wrong letter beats no page.
        assert lettering.width("©", TOY) == lettering.width(" ", TOY)

    def test_the_trailing_gap_of_the_last_letter_is_not_paid_for(self) -> None:
        #  A banner is centred on what it draws, not on what it advanced past.
        assert lettering.width("I", TOY, spacing=Spacing.PROPORTIONAL) == 1


class TestWithTheShippedFace:
    def test_a_word_fits_a_row_where_fixed_setting_would_not(self) -> None:
        acorn = load_font("acorn")
        assert lettering.width("BBC CEEFAX", acorn, spacing=Spacing.FIXED) > 78
        assert lettering.width("BBC CEEFAX", acorn, spacing=Spacing.PROPORTIONAL) <= 78

    def test_and_kerning_takes_something_off_that_again(self) -> None:
        acorn = load_font("acorn")
        proportional = lettering.width("STARDOT", acorn, spacing=Spacing.PROPORTIONAL)
        assert lettering.width("STARDOT", acorn, spacing=Spacing.KERNED) < proportional

    def test_the_letters_stay_apart_however_hard_it_kerns(self) -> None:
        acorn = load_font("acorn")
        rows = drawn(lettering.bitmap("STARDOT", acorn, spacing=Spacing.KERNED))
        assert not any("####" * 3 in row for row in rows)


class TestRefusals:
    def test_a_spacing_that_is_not_one_of_the_three(self) -> None:
        with pytest.raises(ValueError, match="spacing"):
            lettering.width("I", TOY, spacing="sideways")  # type: ignore[arg-type]


class TestIntoCells:
    def test_a_face_of_eight_blocks_needs_three_rows_of_the_frame(self) -> None:
        acorn = load_font("acorn")
        assert lettering.rows_needed(acorn) == 3
        assert len(lettering.cells("STARDOT", acorn)) == 3

    def test_a_margin_can_push_it_to_a_fourth(self) -> None:
        assert lettering.rows_needed(load_font("acorn"), margin=1) == 4

    def test_the_patterns_are_the_ones_the_wire_wants(self) -> None:
        #  The toy I is one block in the top-left of its cell, three rows down.
        assert lettering.cells("I", TOY) == [[0b010101]]

    def test_inverted_lettering_is_a_lit_field_with_holes_in_it(self) -> None:
        #  Which is how teletext has always drawn dark letters: there is no
        #  alpha-black attribute to draw them with.
        assert lettering.cells("I", TOY, inverted=True) == [[0b101010]]

    def test_and_a_margin_is_what_keeps_the_letters_off_its_edge(self) -> None:
        #  A cell of border all round, so the corner of the field is solid.
        field = lettering.cells("I", TOY, inverted=True, margin=3)
        assert field[0][0] == 0b111111


class TestOntoAFrame:
    def test_the_rows_of_a_banner_go_on_consecutive_rows(self) -> None:
        layout = lettering.place(Composition(), 4, "STARDOT", load_font("acorn"))
        assert sorted(layout.runs) == [4, 5, 6]

    def test_and_it_fits_where_the_measurement_said_it_would(self) -> None:
        layout = lettering.place(Composition(), 4, "STARDOT", load_font("acorn"))
        assert layout.fits()

    def test_it_is_centred_unless_a_column_is_given(self) -> None:
        layout = lettering.place(Composition(), 0, "STARDOT", load_font("acorn"))
        run = layout.runs[0][0]
        assert run.column == (COLUMNS - run.cells) // 2

    def test_but_never_at_the_column_the_attribute_needs(self) -> None:
        #  A banner filling the row would otherwise be centred at zero, leaving
        #  the colour attribute nowhere to go.
        #  Thirty-nine cells of toy letters leave one column, and it is the
        #  attribute's; centring would have put the banner in it.
        layout = lettering.place(Composition(), 0, "I" * 39, TOY)
        assert layout.runs[0][0].cells == 39
        assert layout.runs[0][0].column == 1

    def test_and_one_too_wide_for_the_frame_says_so_rather_than_drawing(self) -> None:
        with pytest.raises(DoesNotFit):
            lettering.place(Composition(), 0, "I" * 40, TOY)

    def test_a_banner_costs_one_attribute_on_each_of_its_rows(self) -> None:
        #  The whole argument for a compositor: a row of a banner is one run in
        #  one colour, so it enters graphics once and pays for it once.
        canvas = Canvas(Frame())
        layout = lettering.place(Composition(), 4, "STARDOT", load_font("acorn"), Colour.CYAN)
        layout.draw(canvas)
        for row in (4, 5, 6):
            assert sum(byte < 0x20 for byte in canvas.frame.row_bytes(row)) == 1


def middle_of(layout: Composition) -> float:
    """The middle of the ink of a placed banner, in blocks across the frame."""
    left, right = 0b010101, 0b101010
    lit = [
        (run.column + index) * BLOCKS_ACROSS + half
        for runs in layout.runs.values()
        for run in runs
        for index, pattern in enumerate(run.patterns)
        for half, mask in ((0, left), (1, right))
        if pattern & mask
    ]
    return (min(lit) + max(lit) + 1) / 2


class TestCentringOnTheFrame:
    """Lettering is centred to the block, not to the cell it lands in.

    A cell is two blocks, so centring a banner by whole cells leaves it up to a
    block and a half off -- three quarters of a cell, and plainly visible above
    a line of text that centred itself properly.
    """

    @pytest.mark.parametrize("name", font_names())
    def test_every_face_puts_a_banner_in_the_middle(self, name: str) -> None:
        layout = lettering.place(Composition(), 0, "STARDOT", load_font(name))
        assert abs(middle_of(layout) - COLUMNS * BLOCKS_ACROSS / 2) <= 1

    def test_which_takes_a_blank_block_before_it_when_it_has_to(self) -> None:
        #  console's STARDOT leaves 38 blocks of margin, 19 a side, so the ink
        #  begins half way into a cell. That is a blank block the composition
        #  is given rather than a cell it is denied.
        layout = lettering.place(Composition(), 0, "STARDOT", load_font("console"))
        assert middle_of(layout) == COLUMNS * BLOCKS_ACROSS / 2
        #  The left half of the first cell is blank and the right half is not:
        #  the ink starts in the middle of a cell, which is the whole point.
        assert not layout.runs[0][0].patterns[0] & 0b010101
        assert layout.runs[0][0].patterns[0] & 0b101010

    def test_and_a_column_given_is_still_a_column(self) -> None:
        layout = lettering.place(Composition(), 0, "STARDOT", TOY, column=4)
        assert layout.runs[0][0].column == 4

    def test_a_banner_and_a_rule_share_a_middle(self) -> None:
        #  The complaint that started this: STARDOT sat left of the rule above.
        canvas = Canvas(Frame())
        rule(canvas, 0)
        lettering.place(Composition(), 2, "STARDOT", load_font("boldbash")).draw(canvas)
        assert abs(middle_of_row(canvas, 0) - middle_of_row(canvas, 2)) <= 0.5


class TestLetteringOnAPanel:
    """A word of mosaic lettering in a coloured box, which is what Ceefax did.

    Cyan on blue, red on yellow, blue on green: the box is declared once and
    the lettering says nothing about it.
    """

    def test_the_box_keeps_its_colour_behind_the_letters(self) -> None:
        canvas = Canvas(Frame())
        layout = Composition()
        box = layout.panel(0, 19, width=21, colour=Colour.BLUE, rows=3)
        lettering.place(layout, 0, "NEWS", load_font("silkscreen"), Colour.CYAN, within=box)
        layout.draw(canvas)
        assert canvas.frame.cell(0, 19) == Attribute.NEW_BACKGROUND
        assert not any(
            canvas.frame.cell(row, column) == Attribute.BLACK_BACKGROUND
            for row in (0, 1, 2)
            for column in range(20, COLUMNS)
        )

    def test_and_the_letters_are_centred_in_the_box(self) -> None:
        layout = Composition()
        box = layout.panel(0, 19, width=21, colour=Colour.BLUE, rows=3)
        lettering.place(layout, 0, "NEWS", load_font("silkscreen"), Colour.CYAN, within=box)
        run = layout.runs[0][0]
        assert box.column < run.column and run.end < box.end
        #  Centred within the box, to the block, as it would be on the frame.
        assert abs((run.column + run.end) / 2 - (box.column + box.end) / 2) <= 1

    def test_a_word_too_wide_for_its_box_is_refused(self) -> None:
        layout = Composition()
        box = layout.panel(0, 19, width=21, colour=Colour.BLUE, rows=3)
        with pytest.raises(DoesNotFit):
            lettering.place(layout, 0, "WEATHERMEN", load_font("boldbash"), within=box)


class TestABoxFittedRoundItsLetters:
    """The Ceefax effect in one call: a word in a field of colour.

    The box is fitted here rather than by a caller, because here is where the
    letters can be measured -- and a caller who measured them would then have
    to know that a panel's own first cell goes on the attribute that colours
    it, which is the composition's business and not theirs.
    """

    def test_the_box_is_as_wide_as_the_letters_and_their_padding(self) -> None:
        layout = Composition()
        face = load_font("silkscreen")
        box = lettering.boxed(layout, 0, "NEWS", face, Colour.CYAN, padding=2)
        letters = len(lettering.cells("NEWS", face)[0])
        #  Two cells of colour either side, and one more for the attribute
        #  that colours the box at all.
        assert box.width == letters + 4 + 1

    def test_and_as_deep_as_they_are(self) -> None:
        layout = Composition()
        box = lettering.boxed(layout, 0, "NEWS", load_font("silkscreen"))
        assert len(box.rows) == len(lettering.cells("NEWS", load_font("silkscreen")))

    def test_the_letters_are_inside_it(self) -> None:
        layout = Composition()
        box = lettering.boxed(layout, 0, "NEWS", load_font("silkscreen"))
        run = layout.runs[0][0]
        assert box.column < run.column and run.end <= box.end

    def test_and_centred_in_it_both_ways(self) -> None:
        layout = Composition()
        face = load_font("acorn")
        box = lettering.boxed(layout, 0, "NEWS", face, rows=5)
        rows = sorted(layout.runs)
        assert len(box.rows) == 5
        #  A three-row line in a five-row box: a row of colour above and below.
        assert rows[0] == box.rows[0] + 1
        assert rows[-1] == box.rows[-1] - 1

    def test_a_taller_box_grows_around_the_letters_not_below_them(self) -> None:
        #  So that asking for a box at row 8 puts the letters near row 8.
        layout = Composition()
        box = lettering.boxed(layout, 8, "NEWS", load_font("acorn"), rows=5)
        assert box.rows[0] == 7
        assert sorted(layout.runs)[0] == 8

    def test_it_can_be_put_against_a_side_of_the_frame(self) -> None:
        layout = Composition()
        box = lettering.boxed(layout, 0, "NEWS", load_font("silkscreen"), where=Align.RIGHT)
        assert box.end == COLUMNS

    def test_and_the_box_it_made_can_have_more_put_in_it(self) -> None:
        layout = Composition()
        box = lettering.boxed(layout, 0, "NEWS", load_font("silkscreen"), rows=4)
        layout.text(box.rows[-1], Align.CENTRE, "later", Colour.WHITE, within=box)
        assert layout.fits()

    def test_or_asked_for_the_middle_of_the_frame(self) -> None:
        layout = Composition()
        box = lettering.boxed(
            layout, Align.CENTRE, "NEWS", load_font("acorn"), where=Align.CENTRE
        )
        assert box.rows[0] == (ROWS - len(box.rows)) // 2

    def test_a_box_shorter_than_its_letters_is_refused_as_such(self) -> None:
        #  Because it is not a box: it is a stripe behind them, which is two
        #  things drawn separately and not this function's business.
        layout = Composition()
        with pytest.raises(DoesNotFit, match="stripe"):
            lettering.boxed(layout, 6, "VIEWDATA", load_font("acorn"), rows=1)


class TestAStripeBehindLetteringIsTwoThings:
    """A panel and some lettering, drawn separately and left to the compositor.

    Neither knows about the other. They are both centred, so they line up; the
    row they share is coloured because the composition can see that it is.
    """

    def test_the_row_they_share_takes_the_stripe_s_colour(self) -> None:
        canvas = Canvas(Frame())
        layout = Composition()
        face = load_font("acorn")
        layout.panel(
            7,
            Align.CENTRE,
            width=lettering.cells_needed("VIEWDATA", face, padding=2),
            colour=Colour.BLUE,
        )
        lettering.place(layout, 6, "VIEWDATA", face, Colour.YELLOW)
        layout.draw(canvas)
        assert any(
            canvas.frame.cell(7, column) == Attribute.NEW_BACKGROUND
            for column in range(COLUMNS)
        )
        assert not any(
            canvas.frame.cell(row, column) == Attribute.NEW_BACKGROUND
            for row in (6, 8)
            for column in range(COLUMNS)
        )

    def test_and_the_letters_sit_evenly_above_and_below_it(self) -> None:
        #  A line of letters sits in the middle of the rows it takes, so a
        #  stripe through the middle row has as much of them above it as below.
        face = load_font("acorn")
        picture = lettering.cells("VIEWDATA", face)
        lit = [
            row * BLOCKS_DOWN + third
            for row, patterns in enumerate(picture)
            for third, mask in enumerate((0b000011, 0b001100, 0b110000))
            if any(pattern & mask for pattern in patterns)
        ]
        band = range(BLOCKS_DOWN, 2 * BLOCKS_DOWN)
        assert len([block for block in lit if block < band.start]) == len(
            [block for block in lit if block >= band.stop]
        )

    def test_a_stripe_is_as_wide_as_the_word_and_its_padding(self) -> None:
        face = load_font("acorn")
        bare = lettering.cells_needed("VIEWDATA", face)
        assert lettering.cells_needed("VIEWDATA", face, padding=2) == bare + 4
        assert bare == len(lettering.cells("VIEWDATA", face)[0])
