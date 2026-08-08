"""The four keys that move about a page, drawn as a compass."""

from sextile import keys
from sextile.compass import ROWS, compass
from sextile.viewdata.blocks import BLOCKS_DOWN
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
        assert keys.NEXT_FRAME in rows[8]

    def test_and_each_key_is_beside_its_own_word(self) -> None:
        rows = drawn()
        assert rows[0].strip() == "page up"
        assert rows[9].strip() == "page down"
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
        #  Two rows of arrow above the middle row and two below, with the
        #  middle row's pair reaching into the row under it.
        assert {2, 3, 4, 5, 6, 7} <= set(graphics)

    def test_it_takes_the_rows_it_says_it_does(self) -> None:
        canvas = Canvas(Frame())
        compass(Composition(), 3).draw(canvas)
        assert canvas.frame.last_written_row() == 3 + ROWS - 1

    def test_it_fits_across_the_frame(self) -> None:
        assert compass(Composition(), 0).fits()

    def test_and_can_be_put_lower_down_one(self) -> None:
        assert drawn(6)[6].strip() == "page up"


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


class TestHowItSitsOnTheBlockGrid:
    """The up and down arrows are the same distance from the horizontal pair.

    Measured in blocks, since that is what a reader sees: a row is three of
    them, so a compass that looks even by the row can be a third of one out.
    """

    def test_the_arrows_are_evenly_spaced_about_the_middle(self) -> None:
        canvas = Canvas(Frame())
        compass(Composition(), 0).draw(canvas)
        rows = _ink_rows(canvas)
        above = [block for block in rows if block < 12]
        band = [block for block in rows if 12 <= block < 18]
        below = [block for block in rows if block >= 18]
        assert min(band) - max(above) <= 2
        assert min(below) - max(band) <= 2

    def test_and_the_letters_sit_against_the_arrows_at_both_ends(self) -> None:
        #  W's row runs straight into the up arrow's tip, and the down arrow's
        #  tip straight into S's, with no blank block at either end.
        rows = _ink_rows(Canvas(Frame()))
        assert min(rows) == 2 * BLOCKS_DOWN
        assert max(rows) == 8 * BLOCKS_DOWN - 1


def _ink_rows(canvas: Canvas) -> list[int]:
    """Which block rows of a drawn compass have any mosaic on them."""
    from sextile.viewdata.charset import mosaic_pattern

    compass(Composition(), 0).draw(canvas)
    lit = []
    for row in range(ROWS):
        graphics = False
        for column in range(COLUMNS):
            cell = canvas.frame.cell(row, column)
            graphics = graphics or 0x11 <= cell <= 0x17
            if not graphics or canvas.frame.is_attribute(row, column):
                continue
            pattern = mosaic_pattern(cell)
            for third, mask in enumerate((0b000011, 0b001100, 0b110000)):
                if pattern & mask:
                    lit.append(row * 3 + third)
    return sorted(set(lit))


class TestWhatItCallsThings:
    def test_the_frames_of_a_page_are_called_pages(self) -> None:
        #  A frame is what the wire calls it. To whoever is reading, the frames
        #  of a page are the pages of one document -- and saying so keeps
        #  "previous" and "next" for the other axis, where they mean the items.
        rows = drawn()
        assert "page up" in rows[0] and "page down" in rows[9]
        assert "frame" not in "\n".join(rows)

    def test_and_it_says_the_cursor_keys_work_too(self) -> None:
        assert "arrow keys" in drawn()[ROWS - 1]

    def test_which_they_do(self) -> None:
        #  The claim is only worth making if the framework answers them.
        assert set(keys.ARROWS.values()) == {
            keys.PREVIOUS_FRAME,
            keys.NEXT_FRAME,
            keys.PREVIOUS_ITEM,
            keys.NEXT_ITEM,
        }
