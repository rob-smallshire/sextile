"""Reading MDFS `VDU 23` font files, and what converting one decides."""

import pytest

from mdfs_font import MdfsError, convert, read_mdfs
from sextile.viewdata.font import write_font


def record(code: int, rows: list[str]) -> bytes:
    """One glyph as the file holds it: 23, the code, then eight rows of bits."""
    return bytes([23, code]) + bytes(
        sum(0x80 >> index for index, block in enumerate(row) if block == "#")
        for row in rows
    )


AN_A = [
    "..####..",
    ".##..##.",
    "##....##",
    "########",
    "##....##",
    "##....##",
    "##....##",
    "........",
]
A_SPACE = ["........"] * 8


class TestReadingTheFile:
    def test_a_glyph_comes_back_as_the_picture_it_is(self) -> None:
        assert read_mdfs(record(ord("A"), AN_A))[ord("A")] == AN_A

    def test_the_most_significant_bit_is_the_leftmost_block(self) -> None:
        #  Measured against the real files, not assumed: a face read the other
        #  way round is a mirror image and nothing warns you.
        assert read_mdfs(bytes([23, 65, 0x80, 0, 0, 0, 0, 0, 0, 0]))[65][0] == "#" + "." * 7

    def test_a_file_that_is_not_a_whole_number_of_glyphs(self) -> None:
        with pytest.raises(MdfsError, match="10"):
            read_mdfs(bytes([23, 65, 0, 0, 0]))

    def test_a_record_that_does_not_begin_with_vdu_23(self) -> None:
        with pytest.raises(MdfsError, match="23"):
            read_mdfs(bytes([1, 65] + [0] * 8))


class TestConverting:
    def test_the_face_keeps_its_design_width_for_fixed_setting(self) -> None:
        font = convert(read_mdfs(record(ord("A"), AN_A)), name="X")
        assert font.fixed == 8
        assert font.height == 8

    def test_a_glyph_is_trimmed_to_its_ink(self) -> None:
        glyph = convert(read_mdfs(record(ord("A"), AN_A)), name="X")["A"]
        assert glyph.width == 8

    def test_and_the_columns_trimmed_from_the_left_become_its_bearing(self) -> None:
        narrow = ["...##..."] * 8
        glyph = convert(read_mdfs(record(ord("I"), narrow)), name="X")["I"]
        assert (glyph.width, glyph.bearing) == (2, 3)

    def test_the_advance_is_the_ink_plus_the_tracking(self) -> None:
        narrow = ["...##..."] * 8
        glyph = convert(read_mdfs(record(ord("I"), narrow)), name="X", tracking=2)["I"]
        assert glyph.advance == 4

    def test_a_blank_glyph_has_no_picture_and_the_space_width(self) -> None:
        #  Trimming a space to its ink would leave it no width at all, which is
        #  why the width of a space is a decision the conversion makes.
        space = convert(read_mdfs(record(0x20, A_SPACE)), name="X", space=3)[" "]
        assert (space.width, space.advance) == (0, 3)

    def test_the_provenance_is_written_into_the_font(self) -> None:
        font = convert(
            read_mdfs(record(ord("A"), AN_A)), name="X", source="somewhere", terms="free"
        )
        assert (font.source, font.terms) == ("somewhere", "free")

    def test_what_it_produces_can_be_written_and_read_back(self) -> None:
        font = convert(read_mdfs(record(ord("A"), AN_A)), name="X")
        assert "glyph u+0041 advance 9" in write_font(font)


class TestWhichCodesAreConverted:
    def test_ascii_and_latin_1_come_across_at_their_own_code_points(self) -> None:
        #  Verified against ArcNormal: 0xa3 is a pound sign, 0xe9 an e-acute.
        font = convert(read_mdfs(record(0xA3, AN_A)), name="X")
        assert "£" in font

    def test_the_codes_between_them_are_left_out(self) -> None:
        #  0x80-0x9f hold glyphs in no encoding this project has established.
        #  Guessing at them would put wrong letters on the screen silently.
        font = convert(read_mdfs(record(0x9F, AN_A) + record(0xA3, AN_A)), name="X")
        assert len(font.glyphs) == 1

    def test_as_is_the_solid_block_at_delete(self) -> None:
        font = convert(read_mdfs(record(0x7F, AN_A) + record(0xA3, AN_A)), name="X")
        assert len(font.glyphs) == 1
