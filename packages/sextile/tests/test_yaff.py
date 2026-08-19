"""Reading a YAFF bitmap font into a Sextile `Font`.

The fixtures are hand-written minimal files, not copies of any real font: what
is under test is the reader, and a three-glyph file exercises it where a
thousand-glyph one would only slow it down.
"""

import pytest

from sextile.viewdata.font import FontError
from sextile.viewdata.yaff import read_yaff

#: Three usable glyphs -- a space, a full-cell ``A`` and a narrow ``I`` -- among
#: labels the reader must skip: a device codepoint that is not the character it
#: draws, a codepoint with no character, a tag, and a grapheme cluster.
TINY = """\
name: Tiny
spacing: character-cell
cell-size: 4x5
source-name: tiny.png
copyright: Nobody
notice: Free for testing

# space
u+0020:
    ....
    ....
    ....
    ....
    ....

# capital A; the device codepoint 0x60 is not ASCII 'A'
0x60:
u+0041:
    .@@.
    @..@
    @@@@
    @..@
    @..@

# narrow I, blank columns either side, to test trimming
u+0049:
    .@..
    .@..
    .@..
    .@..
    .@..

# a device codepoint with no character: skipped
0x80:
    @@@@
    @@@@
    @@@@
    @@@@
    @@@@

# a tag label: skipped
"smiley":
    @..@
    ....
    @..@
    .@@.
    ....

# a grapheme cluster: skipped
u+0061, u+0300:
    ....
    .@..
    @.@.
    @@@.
    @.@.
"""


class TestTheHeader:
    def test_it_takes_the_name(self) -> None:
        assert read_yaff(TINY).name == "Tiny"

    def test_the_height_is_the_cell_height_in_blocks(self) -> None:
        assert read_yaff(TINY).height == 5

    def test_the_fixed_width_is_the_cell_width(self) -> None:
        assert read_yaff(TINY).fixed == 4

    def test_the_source_and_terms_come_from_the_metadata(self) -> None:
        #  A hoard font's licence is per-font, so it has to travel into the Font
        #  where the catalogue can show what was loaded.
        font = read_yaff(TINY)
        assert font.source == "tiny.png"
        assert "Nobody" in font.terms
        assert "Free for testing" in font.terms


class TestWhichGlyphsAreKept:
    def test_only_the_ones_with_a_character(self) -> None:
        assert set(read_yaff(TINY).glyphs) == {" ", "A", "I"}

    def test_a_glyph_is_keyed_by_its_character_not_its_device_code(self) -> None:
        #  0x60 is '`' in ASCII but labels the 'A' glyph here, as £ is 0x23 in
        #  the SAA5050 set: keying by the device code would draw the wrong letter.
        font = read_yaff(TINY)
        assert "A" in font
        assert "`" not in font

    def test_a_codepoint_with_no_character_is_dropped(self) -> None:
        assert chr(0x80) not in read_yaff(TINY)


class TestTheGlyphs:
    def test_a_full_cell_glyph_keeps_its_width(self) -> None:
        glyph = read_yaff(TINY)["A"]
        assert glyph.width == 4
        assert glyph.height == 5
        assert glyph.bearing == 0
        assert glyph.advance == 4

    def test_a_narrow_glyph_is_trimmed_and_bears_in(self) -> None:
        #  The blank columns are trimmed away; the left ones become the bearing
        #  and the right ones the gap the advance leaves after the letter.
        glyph = read_yaff(TINY)["I"]
        assert glyph.width == 1
        assert glyph.bearing == 1
        assert glyph.advance == 2

    def test_a_blank_glyph_is_a_space_of_the_cell_width(self) -> None:
        glyph = read_yaff(TINY)[" "]
        assert glyph.width == 0
        assert glyph.advance == 4


class TestWhatIsRefused:
    def test_greyscale_is_refused(self) -> None:
        text = "name: Grey\nlevels: 4\ncell-size: 2x2\n\nu+0041:\n    @.\n    .@\n"
        with pytest.raises(FontError, match="greyscale|level"):
            read_yaff(text)

    def test_a_glyph_of_the_wrong_height_is_refused(self) -> None:
        text = "name: Ragged\ncell-size: 2x3\n\nu+0041:\n    @.\n    .@\n"
        with pytest.raises(FontError, match="tall|height|rows"):
            read_yaff(text)

    def test_a_font_with_no_usable_glyph_is_refused(self) -> None:
        text = 'name: Empty\ncell-size: 2x2\n\n"tag":\n    @.\n    .@\n'
        with pytest.raises(FontError, match="no glyph"):
            read_yaff(text)


class TestItDrawsLikeAnyFace:
    def test_lettering_can_measure_a_word_in_it(self) -> None:
        from sextile.viewdata.lettering import cells_needed, rows_needed

        font = read_yaff(TINY)
        assert rows_needed(font) == 2
        assert cells_needed("AI", font) > 0
