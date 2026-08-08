"""Turning a picture into the blocks a frame can draw."""

from sextile.viewdata.blocks import block_runs, read_bitmap, shifted
from sextile.viewdata.charset import mosaic_code


class TestReadingAPicture:
    def test_hashes_are_lit_and_anything_else_is_not(self) -> None:
        assert read_bitmap(["#.", ".#"]) == [[True, False], [False, True]]


class TestBlockPatterns:
    def test_an_empty_cell_is_no_bits(self) -> None:
        assert block_runs(read_bitmap(["..", "..", ".."])) == [[0b000000]]

    def test_a_full_cell_is_every_bit(self) -> None:
        assert block_runs(read_bitmap(["##", "##", "##"])) == [[0b111111]]

    def test_the_bits_are_in_the_order_the_wire_wants(self) -> None:
        #  Top-left, top-right, middle-left, middle-right, bottom-left,
        #  bottom-right -- the order `mosaic_code` reads them in.
        assert block_runs(read_bitmap(["#.", "..", ".."])) == [[0b000001]]
        assert block_runs(read_bitmap([".#", "..", ".."])) == [[0b000010]]
        assert block_runs(read_bitmap(["..", "..", ".#"])) == [[0b100000]]

    def test_and_so_the_solid_cell_is_the_one_the_rules_use(self) -> None:
        assert mosaic_code(block_runs(read_bitmap(["##", "##", "##"]))[0][0]) == 0x7F

    def test_a_picture_wider_than_a_cell_makes_several(self) -> None:
        assert len(block_runs(read_bitmap(["####", "####", "####"]))[0]) == 2

    def test_a_picture_taller_than_a_cell_makes_several_rows(self) -> None:
        assert len(block_runs(read_bitmap(["##"] * 6)) ) == 2

    def test_it_is_padded_out_to_whole_cells(self) -> None:
        #  Four rows of blocks is two cell-rows, the second mostly empty.
        runs = block_runs(read_bitmap(["##"] * 4))
        assert len(runs) == 2
        assert runs[1] == [0b000011]

    def test_a_short_row_is_taken_as_ending_in_blanks(self) -> None:
        assert block_runs(read_bitmap(["##", "#", ""])) == [[0b000111]]


class TestInverted:
    """A solid field with holes in it, which is how teletext draws dark text."""

    def test_it_turns_the_picture_inside_out(self) -> None:
        assert block_runs(read_bitmap(["#.", "..", ".."]), inverted=True) == [[0b111110]]

    def test_a_blank_picture_becomes_a_solid_field(self) -> None:
        assert block_runs(read_bitmap([".."] * 3), inverted=True) == [[0b111111]]

    def test_and_the_padding_is_lit_too(self) -> None:
        #  Otherwise the field would have a ragged edge where the picture ran
        #  out, which is exactly what an inverted banner must not have.
        runs = block_runs(read_bitmap(["##"] * 4), inverted=True)
        assert runs[1] == [0b111100]

    def test_a_short_row_is_filled_rather_than_left_dark(self) -> None:
        assert block_runs(read_bitmap(["##", "#", ""]), inverted=True) == [[0b111000]]


class TestShiftingByHalfACell:
    def test_a_block_moves_to_the_other_half_of_its_cell(self) -> None:
        assert shifted([0b000001]) == [0b000010]

    def test_and_from_there_into_the_cell_after_it(self) -> None:
        assert shifted([0b000010]) == [0b000000, 0b000001]

    def test_a_row_of_three_blocks_stays_three_blocks(self) -> None:
        assert shifted([0b010101]) == [0b101010]

    def test_the_run_grows_only_when_something_falls_off_the_end(self) -> None:
        assert len(shifted([0b000001, 0b000001])) == 2
        assert len(shifted([0b000001, 0b000010])) == 3

    def test_nothing_shifted_is_nothing(self) -> None:
        assert shifted([]) == []
