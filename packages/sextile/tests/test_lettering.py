"""Setting text in a mosaic font: the three spacings, and what they measure."""

import pytest

from sextile.viewdata import lettering
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Composition, DoesNotFit
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import load_font, read_font
from sextile.viewdata.frame import COLUMNS, Frame
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


class TestWhatIsSet:
    def test_the_lettering_is_as_tall_as_the_face(self) -> None:
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
        assert lettering.rows_for(acorn) == 3
        assert len(lettering.cells("STARDOT", acorn)) == 3

    def test_a_margin_can_push_it_to_a_fourth(self) -> None:
        assert lettering.rows_for(load_font("acorn"), margin=1) == 4

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
