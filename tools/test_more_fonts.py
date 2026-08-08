"""Reading the Lua bitmap fonts from the `more-fonts` collection."""

import pytest

from more_fonts import MoreFontsError, convert, parse


#  A three-by-three face with two letters in it, in the shape the collection
#  keeps: one character to a row of pixels, six bits each, biased by a space,
#  least significant bit leftmost. Every glyph is present, so the strings are
#  256 entries long; all but two of them are blank.
def _face(rows_by_code: dict[int, list[str]], width: int, height: int) -> str:
    def row(bits: str) -> str:
        return chr(0x20 + sum(1 << index for index, bit in enumerate(bits) if bit == "#"))

    data, start, length = [], [], []
    for code in range(256):
        picture = rows_by_code.get(code, ["." * width] * height)
        data += [row(line) for line in picture]
        columns = [
            column
            for column in range(width)
            if any(line[column] == "#" for line in picture)
        ]
        start.append(chr(0x21 + (columns[0] if columns else 0)))
        length.append(chr(0x20 + (columns[-1] - columns[0] + 1 if columns else 0)))
    return (
        "{\n"
        '\tfontname = "Toy",\n'
        '\tauthor = "Nobody",\n'
        '\tsource = "https://example.invalid/toy",\n'
        '\tlicense = "Creative Commons Zero v1.0 Universal",\n'
        f"\tdata = [[{''.join(data)}]],\n"
        f"\tstartX = [[{''.join(start)}]],\n"
        f"\tlengthX = [[{''.join(length)}]],\n"
        f"\tcharW = {width},\n"
        f"\tcharH = {height}\n"
        "}\n"
    )


TOY = _face(
    {
        ord("A"): [".##.", "#..#", "####"],
        ord("I"): [".#..", ".#..", ".#.."],
    },
    width=4,
    height=3,
)


class TestReadingTheFile:
    def test_the_face_says_what_it_is_and_who_made_it(self) -> None:
        face = parse(TOY)
        assert face.fontname == "Toy"
        assert face.author == "Nobody"

    def test_and_on_what_terms_which_is_the_reason_to_read_it(self) -> None:
        #  Each of these fonts carries its own licence, and they are not all
        #  the same one. Losing that on the way in is not an option.
        assert "Creative Commons Zero" in parse(TOY).license

    def test_the_design_size_comes_across(self) -> None:
        assert (parse(TOY).width, parse(TOY).height) == (4, 3)

    def test_a_glyph_is_the_picture_it_looks_like(self) -> None:
        assert parse(TOY).picture(ord("A")) == [".##.", "#..#", "####"]

    def test_the_bounds_of_its_ink_come_with_it(self) -> None:
        #  Which is what makes these worth importing: the proportional metrics
        #  are in the file and do not have to be guessed at.
        assert parse(TOY).bounds(ord("I")) == (1, 1)
        assert parse(TOY).bounds(ord("A")) == (0, 4)

    def test_a_blank_glyph_has_no_ink_and_says_so(self) -> None:
        assert parse(TOY).bounds(ord(" ")) == (0, 0)

    def test_a_file_that_is_not_one_of_these_at_all(self) -> None:
        with pytest.raises(MoreFontsError, match="charW"):
            parse('{ fontname = "X" }')

    def test_a_file_whose_data_is_the_wrong_length_for_its_size(self) -> None:
        with pytest.raises(MoreFontsError, match="256"):
            parse(TOY.replace("charH = 3", "charH = 4"))


class TestTheLongBrackets:
    def test_a_font_whose_data_needs_a_deeper_bracket_is_read_too(self) -> None:
        #  Lua's long strings take a level, and these files use it: a face
        #  with two lit blocks in the right place contains "]]" itself.
        deeper = TOY.replace(" = [[", " = [=[").replace("]],", "]=],")
        assert parse(deeper).picture(ord("A")) == parse(TOY).picture(ord("A"))


class TestConverting:
    def test_the_face_keeps_its_design_width_for_fixed_setting(self) -> None:
        font = convert(parse(TOY))
        assert (font.fixed, font.height) == (4, 3)

    def test_a_glyph_is_trimmed_to_its_ink_and_keeps_its_bearing(self) -> None:
        glyph = convert(parse(TOY))["I"]
        assert (glyph.width, glyph.bearing) == (1, 1)

    def test_the_advance_is_the_ink_plus_the_tracking(self) -> None:
        assert convert(parse(TOY), tracking=2)["I"].advance == 3

    def test_a_blank_glyph_has_no_picture_and_the_space_width(self) -> None:
        assert convert(parse(TOY), space=3)[" "].advance == 3

    def test_the_licence_travels_into_the_font_file(self) -> None:
        font = convert(parse(TOY))
        assert "Creative Commons Zero" in font.terms
        assert "Nobody" in font.source

    def test_it_is_named_for_the_face_unless_told_otherwise(self) -> None:
        assert convert(parse(TOY)).name == "Toy"
        assert convert(parse(TOY), name="Other").name == "Other"


class TestTrimmingBlankRows:
    def test_a_row_blank_in_every_glyph_costs_a_row_of_the_frame(self) -> None:
        #  Several of these faces are drawn in a box taller than the letters,
        #  and three of those blank block-rows is a whole row of the screen.
        padded = _face({ord("A"): ["....", ".##.", "...."]}, width=4, height=3)
        assert convert(parse(padded)).height == 1

    def test_and_the_face_can_be_kept_as_drawn_instead(self) -> None:
        padded = _face({ord("A"): ["....", ".##.", "...."]}, width=4, height=3)
        assert convert(parse(padded), trim=False).height == 3

    def test_a_row_used_by_any_glyph_is_kept_for_all_of_them(self) -> None:
        #  Or the letters no longer sit on the same line as each other.
        assert convert(parse(TOY))["I"].height == 3


class TestWhichCodesAreConverted:
    def test_ascii_comes_across(self) -> None:
        assert "A" in convert(parse(TOY))

    def test_and_nothing_above_it_does(self) -> None:
        #  These files hold 256 glyphs in an encoding the collection does not
        #  state. Guessing at it would put wrong letters on the screen.
        high = _face({0xA3: ["####", "####", "####"]}, width=4, height=3)
        assert "£" not in convert(parse(high))
