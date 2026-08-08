"""The four keys that move about a page, drawn as a compass."""

from sextile import keys
from sextile.compass import ROWS, compass
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Composition
from sextile.viewdata.frame import COLUMNS, Frame


def drawn(row: int = 0) -> list[str]:
    canvas = Canvas(Frame())
    compass(Composition(), row).draw(canvas)
    characters, _ = canvas.frame.to_grid()
    return characters


class TestWhatItSays:
    def test_every_key_it_names_is_one_the_framework_sends(self) -> None:
        #  Written nowhere: the keys come from `keys`, so a compass cannot be
        #  drawn for keys the framework has stopped answering.
        shown = "\n".join(drawn())
        for key in (
            keys.PREVIOUS_FRAME,
            keys.NEXT_FRAME,
            keys.PREVIOUS_ITEM,
            keys.NEXT_ITEM,
        ):
            assert f" {key} " in shown or shown.count(key) > 0

    def test_the_frame_keys_are_above_and_below_the_item_keys(self) -> None:
        rows = drawn()
        assert keys.PREVIOUS_FRAME in rows[1]
        assert keys.PREVIOUS_ITEM in rows[4] and keys.NEXT_ITEM in rows[4]
        assert keys.NEXT_FRAME in rows[9]

    def test_and_each_key_is_beside_its_own_word(self) -> None:
        rows = drawn()
        assert rows[0].strip() == "previous frame"
        assert rows[10].strip() == "next frame"
        assert rows[4].index(keys.PREVIOUS_ITEM) > rows[4].index("previous")
        assert rows[4].index(keys.NEXT_ITEM) < rows[4].index("next")


class TestWhatItDraws:
    def test_the_arrows_are_mosaics_and_not_letters(self) -> None:
        #  The character set has no down arrow, so all four are drawn: three
        #  letters beside one picture would look like a mistake.
        canvas = Canvas(Frame())
        compass(Composition(), 0).draw(canvas)
        graphics = [
            row
            for row in range(ROWS)
            if any(canvas.frame.is_attribute(row, column) for column in range(COLUMNS))
        ]
        #  Two rows of arrow above the middle row, two below, and the middle
        #  row's pair reaching into the row under it.
        assert {2, 3, 4, 5, 7, 8} <= set(graphics)

    def test_it_takes_the_rows_it_says_it_does(self) -> None:
        canvas = Canvas(Frame())
        compass(Composition(), 3).draw(canvas)
        assert canvas.frame.last_written_row() == 3 + ROWS - 1

    def test_it_fits_across_the_frame(self) -> None:
        assert compass(Composition(), 0).fits()

    def test_and_can_be_put_lower_down_one(self) -> None:
        assert drawn(6)[6].strip() == "previous frame"


class TestTheArrowsThemselves:
    def test_each_is_a_quarter_turn_of_the_last(self) -> None:
        #  Which is what keeps the four looking like one set, and is why only
        #  one of them is drawn in the source.
        from sextile.compass import _DOWN, _LEFT, _RIGHT, _UP

        assert _RIGHT.turned() == _UP
        assert _UP.turned() == _LEFT
        assert _LEFT.turned() == _DOWN
        assert _DOWN.turned() == _RIGHT

    def test_and_each_fits_three_cells_by_two_rows(self) -> None:
        from sextile.compass import _DOWN, _LEFT, _RIGHT, _UP

        for arrow in (_UP, _DOWN, _LEFT, _RIGHT):
            assert arrow.cells_across <= 3
            assert arrow.rows <= 2
