"""Series drawn on the block grid.

What is tested is the shape of the bitmap rather than how it looks: that a
value lands where it is asked to, that a line is joined rather than dotted,
that a gap in the data is a gap in the line.
"""

from sextile.viewdata.charting import bars, curve


def drawn(grid: list[list[bool]]) -> list[str]:
    return ["".join("#" if lit else "." for lit in row) for row in grid]


def lit_in(grid: list[list[bool]], column: int) -> list[int]:
    """Which block rows are lit in a column, counted from the bottom."""
    down = len(grid)
    return [down - 1 - row for row, cells in enumerate(grid) if cells[column]]


class TestACurve:
    def test_a_level_series_is_a_level_line(self) -> None:
        assert drawn(curve([0.5, 0.5], across=8, down=3)) == [
            "........",
            "########",
            "........",
        ]

    def test_the_bottom_of_the_region_is_nought_and_the_top_is_one(self) -> None:
        assert lit_in(curve([0.0, 0.0], across=4, down=3), 0) == [0]
        assert lit_in(curve([1.0, 1.0], across=4, down=3), 0) == [2]

    def test_a_value_sits_in_the_middle_of_its_share_of_the_width(self) -> None:
        #  So that a chart lines up with the labels or pictures above it. Two
        #  values over eight blocks put them at three and a half and seven and
        #  a half, not at nought and seven.
        rising = curve([0.0, 1.0], across=8, down=3)
        assert lit_in(rising, 0) == [0]
        assert lit_in(rising, 7) == [2]

    def test_and_the_line_runs_level_out_to_the_edges(self) -> None:
        #  It is the last thing known, and a line that stopped short would read
        #  as data that stopped.
        assert lit_in(curve([0.5, 0.5], across=8, down=3), 0) == [1]
        assert lit_in(curve([0.5, 0.5], across=8, down=3), 7) == [1]

    def test_a_step_is_joined_rather_than_dotted(self) -> None:
        #  At nine blocks tall a step of three is common, and a line of
        #  unconnected marks does not read as a line.
        steep = curve([0.0, 1.0], across=4, down=9)
        for column in range(4):
            assert lit_in(steep, column), column
        every = sorted({level for column in range(4) for level in lit_in(steep, column)})
        assert every == list(range(9))

    def test_a_missing_value_breaks_it(self) -> None:
        #  There is no interpolating across a gap: joining the ends would draw
        #  a claim about an hour we have nothing for.
        gapped = curve([0.0, None, 1.0], across=12, down=3)
        assert any(not any(row[column] for row in gapped) for column in range(12))

    def test_nothing_to_plot_is_an_empty_region(self) -> None:
        assert drawn(curve([], across=4, down=3)) == ["...."] * 3


class TestBars:
    def test_each_takes_its_whole_share_of_the_width(self) -> None:
        #  A quantity per hour has no gap between one hour and the next.
        assert drawn(bars([1.0, 0.0], across=4, down=3)) == [
            "##..",
            "##..",
            "##..",
        ]

    def test_they_stand_on_the_bottom(self) -> None:
        assert drawn(bars([1 / 3], across=2, down=3)) == ["..", "..", "##"]

    def test_nothing_is_no_bar_at_all(self) -> None:
        assert drawn(bars([0.0], across=2, down=3)) == [".."] * 3

    def test_a_missing_value_is_not_a_nought(self) -> None:
        assert drawn(bars([None], across=2, down=3)) == [".."] * 3
