"""Handing the terminal back when the line drops.

Every frame begins by hiding the cursor, because a cursor trailing across the
screen as a page paints is a distraction. But once the service has rung off the
reader is talking to their modem again -- `+++`, `ATDT`, whatever their comms
software wants -- and a terminal with no cursor, sitting under a full screen of
somebody else's frame, gives them nothing to type at.

So the last thing sent is the cursor, put somewhere there is room to type.
"""

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import ROWS, Frame
from sextile.viewdata.parting import parting_bytes


def written_to(row: int) -> Frame:
    canvas = Canvas()
    canvas.row(row).text("something")
    return canvas.frame


class TestTheCursorComesBack:
    def test_it_is_turned_on(self) -> None:
        assert ScreenControl.CURSOR_ON in parting_bytes(written_to(3))

    def test_it_is_turned_on_last_of_all(self) -> None:
        #  So that it appears where it will be, rather than travelling there in
        #  view of the reader.
        assert parting_bytes(written_to(3))[-1] == ScreenControl.CURSOR_ON

    def test_the_screen_is_not_cleared(self) -> None:
        #  The parting frame has to survive: it is what says goodbye.
        assert 0x0C not in parting_bytes(written_to(3))

    def test_every_byte_survives_a_seven_bit_line(self) -> None:
        assert all(byte < 0x80 for byte in parting_bytes(written_to(3)))


class TestWhereItIsLeft:
    def test_below_the_last_row_with_anything_on_it(self) -> None:
        #  Two rows down: one blank line between the message and where the
        #  reader types, which reads as a gap rather than a collision.
        assert _rows_down(parting_bytes(written_to(3))) == 2

    def test_at_the_start_of_the_row(self) -> None:
        assert parting_bytes(written_to(3)).startswith(
            bytes([ScreenControl.CARRIAGE_RETURN])
        )

    def test_a_page_reaching_the_last_row_but_one_moves_down_only_once(self) -> None:
        assert _rows_down(parting_bytes(written_to(ROWS - 2))) == 1

    def test_a_page_reaching_the_bottom_stays_on_the_bottom_row(self) -> None:
        #  There is nowhere below it, and a line feed there wraps to the top of
        #  the frame the service has just drawn.
        assert _rows_down(parting_bytes(written_to(ROWS - 1))) == 0

    def test_a_blank_page_leaves_the_cursor_near_the_top(self) -> None:
        assert _rows_down(parting_bytes(Frame())) == 2


def _rows_down(data: bytes) -> int:
    return data.count(ScreenControl.LINE_FEED)
