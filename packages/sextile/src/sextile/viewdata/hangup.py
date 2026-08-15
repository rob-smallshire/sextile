"""Handing the terminal back when the line drops.

Every frame begins by hiding the cursor: one trailing across the screen as a
page paints is a distraction, and it is turned back on only where a reader is
typing. But once the service has rung off, the reader is talking to
their modem again -- `+++`, `ATDT` and whatever else their comms software wants
-- and a terminal with no cursor, sitting under a full screen of somebody else's
frame, gives them nothing to type at.

So the last thing sent down the line is the cursor, put where there is room to
type. Two rows below the goodbye, which reads as a gap rather than a collision;
less if the page reached the bottom of the screen, since a line feed on row 23
wraps to the top of the frame just drawn rather than scrolling it.
"""

from typing import Final

from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import ROWS, Frame

#: Rows between the last thing said and where the reader is left to type.
_GAP: Final = 2


def hangup_bytes(frame: Frame) -> bytes:
    """Leave the cursor somewhere the reader can talk to their modem.

    Sent after a parting frame, whose own trailing blanks are not transmitted --
    so the cursor is sitting just after the last thing written, and this walks
    it on from there.
    """
    spare = ROWS - 1 - frame.last_written_row()
    down = max(min(_GAP, spare), 0)
    return (
        bytes([ScreenControl.CARRIAGE_RETURN])
        + bytes([ScreenControl.LINE_FEED, ScreenControl.CARRIAGE_RETURN]) * down
        + bytes([ScreenControl.CURSOR_ON])
    )
