"""Small pictures written in the source as the pictures they are."""

from sextile.viewdata.blocks import icon

ARROW = icon("""
   #
    #
######
    #
   #
""")


def art(shape: object) -> list[str]:
    assert hasattr(shape, "bitmap")
    return ["".join("#" if block else "." for block in row) for row in shape.bitmap]


class TestReadingOne:
    def test_it_is_the_picture_it_looks_like(self) -> None:
        assert art(ARROW) == ["...#..", "....#.", "######", "....#.", "...#.."]

    def test_the_indentation_the_code_needed_goes(self) -> None:
        #  The common part of it: what one row is drawn further along than
        #  another is the picture, and stays.
        assert art(icon("""
            ##
             #
        """)) == ["##", ".#"]

    def test_and_the_blank_lines_at_either_end(self) -> None:
        assert icon("\n\n##\n\n").down == 1

    def test_it_can_be_drawn_in_dots_or_in_spaces(self) -> None:
        assert art(icon("#.#\n.#.")) == art(icon("# #\n # "))

    def test_something_else_can_be_the_lit_block(self) -> None:
        assert art(icon("XX\nX.", lit="X")) == ["##", "#."]

    def test_it_knows_how_much_of_a_frame_it_takes(self) -> None:
        assert (ARROW.across, ARROW.down) == (6, 5)
        assert (ARROW.cells_across, ARROW.rows) == (3, 2)


class TestTurningOne:
    def test_a_quarter_turn_stands_it_up(self) -> None:
        assert art(ARROW.turned()) == [
            "..#..",
            ".###.",
            "#.#.#",
            "..#..",
            "..#..",
            "..#..",
        ]

    def test_four_of_them_come_back_to_where_they_started(self) -> None:
        assert ARROW.turned(4) == ARROW

    def test_and_the_way_round_is_anticlockwise(self) -> None:
        #  A right arrow turned once points up, which is the order a set of
        #  four is written in -- so a block in the top-left corner comes round
        #  to the bottom-left.
        assert art(icon("#.\n..").turned()) == ["..", "#."]


class TestIntoCells:
    def test_it_comes_out_as_mosaic_patterns(self) -> None:
        assert icon("##\n##\n##").cells() == [[0b111111]]

    def test_padded_out_to_whole_cells(self) -> None:
        assert len(ARROW.cells()) == ARROW.rows

    def test_and_can_be_had_the_other_way_round(self) -> None:
        assert icon("##\n##\n##").cells(inverted=True) == [[0b000000]]
