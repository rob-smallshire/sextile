"""Showing a frame in a modern terminal, for development without a Beeb.

The mosaic mapping is the interesting part. A teletext graphics character is a
2x3 grid of blocks encoded in the character code's bits, and Unicode's Symbols
for Legacy Computing block has a codepoint for every one of those 64 patterns --
so a frame can be shown as the Beeb would draw it rather than approximated.
"""

import pytest

from sextile.viewdata.ansi import mosaic_character, render_ansi, sextant
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Attribute, Colour
from sextile.viewdata.frame import COLUMNS, ROWS, Frame


class TestSextants:
    def test_the_empty_pattern_is_a_space(self) -> None:
        assert sextant(0b000000) == " "

    def test_the_full_pattern_is_a_full_block(self) -> None:
        assert sextant(0b111111) == "█"

    def test_the_left_column_is_a_left_half_block(self) -> None:
        #  Unicode already had this one, so the sextant block skips it.
        assert sextant(0b010101) == "▌"

    def test_the_right_column_is_a_right_half_block(self) -> None:
        assert sextant(0b101010) == "▐"

    def test_the_first_sextant_is_the_top_left_block(self) -> None:
        assert sextant(0b000001) == "\U0001fb00"

    def test_the_last_sextant(self) -> None:
        assert sextant(0b111110) == "\U0001fb3b"

    @pytest.mark.parametrize("pattern", range(64))
    def test_every_pattern_maps_to_exactly_one_character(self, pattern: int) -> None:
        assert len(sextant(pattern)) == 1

    def test_the_mapping_is_a_bijection(self) -> None:
        assert len({sextant(pattern) for pattern in range(64)}) == 64

    @pytest.mark.parametrize("pattern", [-1, 64, 100])
    def test_patterns_outside_six_bits_are_rejected(self, pattern: int) -> None:
        with pytest.raises(ValueError):
            sextant(pattern)


class TestMosaicCharacters:
    def test_the_graphics_space_is_blank(self) -> None:
        assert mosaic_character(0x20) == " "

    def test_the_solid_graphics_character_is_a_full_block(self) -> None:
        assert mosaic_character(0x7F) == "█"

    def test_the_sixth_block_is_carried_by_bit_six(self) -> None:
        #  Bit 5 selects the graphics range itself -- which is why 0x40-0x5F
        #  show letters -- so the bottom-right block is carried by bit 6.
        assert mosaic_character(0x60) == sextant(0b100000)

    def test_letters_are_shown_in_the_middle_of_the_graphics_range(self) -> None:
        #  In graphics mode 0x40-0x5F still display as alphanumerics.
        assert mosaic_character(0x41) == "A"

    @pytest.mark.parametrize("code", [0x00, 0x1F, 0x80])
    def test_codes_outside_the_displayable_range_are_rejected(self, code: int) -> None:
        with pytest.raises(ValueError):
            mosaic_character(code)


class TestRendering:
    def test_a_blank_frame_renders_as_24_rows(self) -> None:
        rendered = render_ansi(Frame(), colour=False)
        assert rendered.splitlines() == [" " * COLUMNS] * ROWS

    def test_text_appears(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("STARDOT")
        assert "STARDOT" in render_ansi(canvas.frame, colour=False)

    def test_an_attribute_shows_as_a_space(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("RED", Colour.RED)
        assert render_ansi(canvas.frame, colour=False).splitlines()[0].startswith(" RED")

    def test_colour_emits_escape_sequences(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("RED", Colour.RED)
        assert "\x1b[" in render_ansi(canvas.frame, colour=True)

    def test_without_colour_no_escape_sequences_are_emitted(self) -> None:
        canvas = Canvas()
        canvas.row(0).text("RED", Colour.RED)
        assert "\x1b[" not in render_ansi(canvas.frame, colour=False)

    def test_graphics_cells_render_as_mosaics(self) -> None:
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.GRAPHICS_WHITE)
        frame.write(0, 1, "\u25ae")  # 0x7F, solid in graphics mode
        assert "█" in render_ansi(frame, colour=False)

    def test_graphics_state_does_not_leak_into_the_next_row(self) -> None:
        #  Attributes reset each row, so row 1 is alphanumeric again.
        frame = Frame()
        frame.set_attribute(0, 0, Attribute.GRAPHICS_WHITE)
        frame.write(1, 0, "\u25ae")
        assert render_ansi(frame, colour=False).splitlines()[1][0] == "▮"
