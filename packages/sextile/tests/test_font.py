"""The mosaic font format, and reading it."""

from importlib import resources

import pytest

from sextile.viewdata.font import (
    FontError,
    Glyph,
    font_names,
    load_font,
    read_font,
    write_font,
)

A_FONT = """\
name: Example
source: invented for the tests
terms: MIT, with the rest of Sextile
height: 5
fixed: 6

glyph u+0020 advance 3

glyph u+0041 advance 5   A
.##.
#..#
####
#..#
#..#

glyph u+002E advance 2   .
..
..
..
..
#.
"""


class TestTheHeader:
    def test_it_carries_the_name(self) -> None:
        assert read_font(A_FONT).name == "Example"

    def test_and_where_the_face_came_from_and_on_what_terms(self) -> None:
        font = read_font(A_FONT)
        #  A font's licence has to travel with the font, or it is lost the
        #  first time the file is copied.
        assert font.source == "invented for the tests"
        assert font.terms == "MIT, with the rest of Sextile"

    def test_it_gives_the_height_in_blocks(self) -> None:
        assert read_font(A_FONT).height == 5

    def test_and_the_advance_a_fixed_width_face_uses(self) -> None:
        assert read_font(A_FONT).fixed == 6

    def test_a_missing_field_is_refused_by_name(self) -> None:
        with pytest.raises(FontError, match="height"):
            read_font("name: Nameless\nfixed: 6\n\nglyph u+0041 advance 1\n#\n")

    def test_an_unknown_field_is_refused_rather_than_ignored(self) -> None:
        #  Silently dropping it would lose provenance to a typo.
        with pytest.raises(FontError, match="weight"):
            read_font("name: X\nheight: 1\nfixed: 1\nweight: bold\n")

    def test_a_field_that_should_be_a_number_and_is_not(self) -> None:
        with pytest.raises(FontError, match="height"):
            read_font("name: X\nheight: tall\nfixed: 1\n")


class TestGlyphs:
    def test_a_glyph_is_found_by_its_character(self) -> None:
        assert read_font(A_FONT)["A"].advance == 5

    def test_the_picture_is_read_as_the_picture_it_looks_like(self) -> None:
        assert read_font(A_FONT)["A"].bitmap[0] == (False, True, True, False)

    def test_a_glyph_is_as_wide_as_its_widest_row(self) -> None:
        assert read_font(A_FONT)["A"].width == 4

    def test_and_the_advance_is_its_own_business_not_its_width(self) -> None:
        #  The gap after a letter belongs to the font; a renderer that trimmed
        #  at draw time would re-decide it on every frame.
        assert read_font(A_FONT)["A"].advance == 5

    def test_a_glyph_with_no_picture_is_blank_but_still_advances(self) -> None:
        space = read_font(A_FONT)[" "]
        assert space.width == 0
        assert space.advance == 3

    def test_short_rows_are_taken_as_ending_in_blanks(self) -> None:
        font = read_font("name: X\nheight: 2\nfixed: 2\n\nglyph u+0041 advance 3\n##\n#\n")
        assert font["A"].bitmap[1] == (True, False)

    def test_a_picture_of_the_wrong_height_is_refused(self) -> None:
        with pytest.raises(FontError, match="u\\+0041"):
            read_font("name: X\nheight: 3\nfixed: 3\n\nglyph u+0041 advance 3\n##\n")

    def test_a_glyph_says_where_its_ink_sat_in_the_design_width(self) -> None:
        #  Trimmed pictures make a proportional setting easy and a fixed one
        #  impossible, unless the bearing that was trimmed away is kept.
        font = read_font(
            "name: X\nheight: 1\nfixed: 8\n\nglyph u+0041 advance 3 bearing 2\n##\n"
        )
        assert font["A"].bearing == 2

    def test_and_most_glyphs_have_none_so_it_may_be_left_out(self) -> None:
        assert read_font(A_FONT)["A"].bearing == 0

    def test_a_bearing_that_is_not_a_number(self) -> None:
        with pytest.raises(FontError, match="bearing"):
            read_font(
                "name: X\nheight: 1\nfixed: 8\n\nglyph u+0041 advance 3 bearing x\n#\n"
            )

    def test_a_character_the_font_has_no_glyph_for(self) -> None:
        assert "Z" not in read_font(A_FONT)

    def test_and_asking_for_it_substitutes_rather_than_raising(self) -> None:
        #  As transliteration does, and with the same question mark. A banner
        #  with one wrong letter is a better answer than no page at all.
        font = read_font(A_FONT + "\nglyph u+003f advance 4   ?\n#\n.\n#\n.\n#\n")
        assert font.glyph("Z") == font["?"]

    def test_and_a_font_without_even_a_question_mark_leaves_a_gap(self) -> None:
        font = read_font("name: X\nheight: 1\nfixed: 4\n\nglyph u+0041 advance 2\n#\n")
        blank = font.glyph("Z")
        assert blank.width == 0
        assert blank.advance == font.fixed


class TestMalformedFiles:
    def test_a_picture_before_any_glyph(self) -> None:
        with pytest.raises(FontError, match="glyph"):
            read_font("name: X\nheight: 1\nfixed: 1\n\n####\n")

    def test_a_glyph_line_without_an_advance(self) -> None:
        with pytest.raises(FontError, match="advance"):
            read_font("name: X\nheight: 1\nfixed: 1\n\nglyph u+0041\n#\n")

    def test_a_glyph_named_as_something_other_than_a_code_point(self) -> None:
        with pytest.raises(FontError, match="u\\+"):
            read_font("name: X\nheight: 1\nfixed: 1\n\nglyph A advance 2\n#\n")

    def test_the_same_character_twice(self) -> None:
        with pytest.raises(FontError, match="u\\+0041"):
            read_font(
                "name: X\nheight: 1\nfixed: 1\n"
                "\nglyph u+0041 advance 2\n#\n"
                "\nglyph u+0041 advance 2\n#\n"
            )

    def test_a_line_that_is_neither_a_field_nor_a_picture(self) -> None:
        with pytest.raises(FontError, match="line 5"):
            read_font("name: X\nheight: 1\nfixed: 1\n\nwhat is this\n")

    def test_a_font_with_no_glyphs_at_all(self) -> None:
        with pytest.raises(FontError, match="no glyphs"):
            read_font("name: X\nheight: 1\nfixed: 1\n")


class TestWritingItBackOut:
    def test_what_is_written_reads_back_the_same(self) -> None:
        #  The converters write this format; a round trip is what says they may
        #  be trusted to.
        assert read_font(write_font(read_font(A_FONT))) == read_font(A_FONT)

    def test_and_it_is_written_as_the_picture_it_is(self) -> None:
        assert "\n.##.\n#..#\n####\n" in write_font(read_font(A_FONT))

    def test_glyphs_come_out_in_code_point_order(self) -> None:
        written = write_font(read_font(A_FONT))
        assert written.index("u+0020") < written.index("u+002e") < written.index("u+0041")

    def test_a_bearing_is_written_only_when_there_is_one(self) -> None:
        font = read_font(
            "name: X\nheight: 1\nfixed: 8\n\nglyph u+0041 advance 3 bearing 2  A\n##\n"
        )
        assert "glyph u+0041 advance 3 bearing 2  A" in write_font(font)
        assert read_font(write_font(font))["A"].bearing == 2

    def test_the_note_beside_each_glyph_says_which_letter_it_is(self) -> None:
        #  So that the file can be read, which is the point of the format.
        assert "glyph u+0041 advance 5  A" in write_font(read_font(A_FONT))

    def test_a_character_that_would_not_survive_being_written_has_no_note(self) -> None:
        font = read_font("name: X\nheight: 1\nfixed: 1\n\nglyph u+000a advance 2\n#\n")
        assert "glyph u+000a advance 2\n" in write_font(font)


class TestAGlyphOnItsOwn:
    def test_it_can_be_made_from_a_picture(self) -> None:
        glyph = Glyph.of(["##", ".#"], advance=3)
        assert glyph.bitmap == ((True, True), (False, True))
        assert glyph.height == 2
        assert glyph.bearing == 0


class TestTheFacesTheFrameworkShips:
    def test_there_is_a_default_to_letter_a_banner_with(self) -> None:
        assert "acorn" in font_names()

    def test_and_a_choice_of_sizes_beside_it(self) -> None:
        heights = {load_font(name).height for name in font_names()}
        #  Three blocks is a single row of the frame; seventeen is six.
        assert min(heights) <= 3
        assert max(heights) >= 16

    @pytest.mark.parametrize("name", font_names())
    def test_every_face_shipped_reads(self, name: str) -> None:
        assert load_font(name).glyphs

    @pytest.mark.parametrize("name", font_names())
    def test_every_face_can_set_a_banner(self, name: str) -> None:
        font = load_font(name)
        assert all(character in font for character in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ")

    @pytest.mark.parametrize("name", font_names())
    def test_every_face_says_where_it_came_from_and_on_what_terms(
        self, name: str
    ) -> None:
        #  A font whose licence has gone missing cannot be shipped, and this
        #  is what stops one being added without it.
        font = load_font(name)
        assert font.source and font.terms

    @pytest.mark.parametrize("name", font_names())
    def test_no_face_is_called_by_a_name_its_licence_reserves(
        self, name: str
    ) -> None:
        #  Converting a font to another format makes a Modified Version under
        #  the Open Font License, which may not use the reserved name. The
        #  attribution belongs in the source line, and that is where it is.
        reserved = ("dogica", "quinquefive", "pixeloid", "times9k", "birchleaf")
        assert not any(word in name.replace("-", "") for word in reserved)
        assert not any(word in load_font(name).name.lower().replace(" ", "") for word in reserved)

    def test_the_licence_ships_beside_the_faces_it_covers(self) -> None:
        #  The Open Font License requires that a copy travel with the font,
        #  so it is package data rather than a file in the repository root.
        licence = resources.files("sextile.viewdata.fonts").joinpath("OFL-1.1.txt")
        assert "SIL OPEN FONT LICENSE Version 1.1" in licence.read_text(encoding="utf-8")

    def test_and_every_face_it_covers_names_it(self) -> None:
        licence = (
            resources.files("sextile.viewdata.fonts")
            .joinpath("OFL-1.1.txt")
            .read_text(encoding="utf-8")
        )
        for name in font_names():
            if "Open Font License" in load_font(name).terms:
                assert f"{name}.font" in licence

    def test_it_loads_and_is_the_size_it_was_drawn(self) -> None:
        acorn = load_font("acorn")
        assert acorn.height == 8
        assert acorn.fixed == 8

    def test_it_has_the_repertoire_a_page_will_ask_for(self) -> None:
        acorn = load_font("acorn")
        #  Sterling among them: a Viewdata service on this side of the water
        #  will want it, and the G0 set has it where ASCII has a hash.
        assert all(character in acorn for character in "STARDOT viewdata 0123456789£?")

    def test_and_it_says_where_it_came_from(self) -> None:
        #  The licence travels in the file, not only in NOTICE.md.
        assert "MDFS" in load_font("acorn").source
        assert load_font("acorn").terms

    def test_the_letters_are_trimmed_and_carry_their_bearings(self) -> None:
        letter_i = load_font("acorn")["i"]
        assert letter_i.width < load_font("acorn").fixed
        assert letter_i.bearing > 0

    def test_a_face_that_is_not_shipped_says_what_is(self) -> None:
        with pytest.raises(FontError, match="acorn"):
            load_font("helvetica")
