"""Redrawing part of a frame that is already on screen.

The command line does this for one row. A form does it for several: a field the
reader is typing into, and the suggestions beneath it that change as they type.
A whole frame is eight seconds at 1200 baud and a block of three rows is one, so
which of the two a keystroke costs is the difference between a search that works
and a search that cannot be used.

Everything here rests on what `docs/spikes/spike_suggestion_block.py` measured
against real Commstar, and one finding in particular that no arithmetic would
have produced:

**A row written to all forty columns must not be followed by a cursor down.** It
wraps of its own accord, so the cursor is already on the next row and the
carriage return and cursor down that walk to the next row of the block move it
down a second one. A three-row block written full width lands on rows 4, 6 and 8
and overruns what is beneath it.

Two things follow. Every row is sent **trimmed to its last non-blank cell**,
which is what makes the walk right for the ordinary case and costs a third
fewer bytes into the bargain. And a row that genuinely does fill all forty
columns is not refused but **accounted for**: the wrap has already moved the
cursor to column zero of the next row, so the step after it is one fewer, and
needs no carriage return.
"""

from collections.abc import Iterable, Sequence
from typing import Final

from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import COLUMNS, Frame

#: What a repaint of no rows costs.
NOTHING: Final = b""


def changed_rows(before: Frame, after: Frame, within: Iterable[int]) -> list[int]:
    """Which of these rows differ between two frames, in order.

    Typing narrows a list of suggestions, so most keystrokes leave the top of
    it alone. Sending only what moved is what makes the common keystroke cost
    forty bytes rather than a hundred and twenty.
    """
    return [row for row in sorted(within) if _row_of(before, row) != _row_of(after, row)]


def rows_bytes(
    frame: Frame,
    rows: Sequence[int],
    *,
    was: Frame | None = None,
    caret: tuple[int, int] | None = None,
) -> bytes:
    """Redraw these rows of a frame already on screen, and place the cursor.

    ``was`` is the frame as the terminal currently has it, and is what decides
    how much of each row to send: **the wider of the old row and the new one**.
    A row that has grown shorter must blank what it vacated, or the tail of the
    longer thing that was there stays on screen -- which on a suggestion list
    means a place the reader has typed past still offering itself.

    ``caret`` is where to leave the cursor, and it is turned on there: the
    reader is in the middle of a word and needs to see where the next letter
    lands.
    """
    if not rows:
        return NOTHING
    out = bytearray()
    at = 0
    wrapped = False
    for row in rows:
        if not out:
            out += _to_row(row)
        elif wrapped:
            #  The row before filled all forty columns and wrapped, so the
            #  cursor is already at column zero of the row after it. A carriage
            #  return would do nothing and a cursor down would overshoot.
            out += bytes([ScreenControl.LINE_FEED]) * (row - at - 1)
        else:
            #  Carriage return to column zero, then one cursor down per row
            #  stepped over. Moving erases nothing, which is what lets the rows
            #  in between be left alone.
            out += bytes([ScreenControl.CARRIAGE_RETURN])
            out += bytes([ScreenControl.LINE_FEED]) * (row - at)
        width = frame.used_columns(row)
        if was is not None:
            width = max(width, was.used_columns(row))
        out += frame.row_bytes(row, upto=width)
        wrapped = width == COLUMNS
        at = row
    if caret is not None:
        out += _to_caret(*caret)
    return bytes(out)


def _row_of(frame: Frame, row: int) -> bytes:
    return bytes(frame.row_bytes(row))


def _to_row(row: int) -> bytes:
    """Home, then down. The only positioning viewdata has."""
    return bytes([ScreenControl.CURSOR_HOME]) + bytes([ScreenControl.LINE_FEED]) * row


def _to_caret(row: int, column: int) -> bytes:
    """Put the cursor at a cell and show it.

    Cursor right skips without erasing -- measured -- so walking across a row
    already drawn disturbs nothing. Cheaper than it looks: a field is near the
    top of a frame and the caret near the start of a row.
    """
    if not 0 <= column <= COLUMNS:
        raise ValueError(f"column {column} is not on a {COLUMNS}-column row")
    return (
        _to_row(row)
        + bytes([ScreenControl.CURSOR_RIGHT]) * column
        + bytes([ScreenControl.CURSOR_ON])
    )
