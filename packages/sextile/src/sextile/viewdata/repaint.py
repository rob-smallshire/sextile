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

from sextile.viewdata.encoding import ScreenControl, encode_text
from sextile.viewdata.frame import COLUMNS, ROWS, Frame

#: What a repaint of no rows costs.
NOTHING: Final = b""

#: An empty cell, which is also the space that covers a rubbed-out character.
_BLANK: Final = 0x20


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
    means an entry the reader has typed past still offering itself.

    ``caret`` is where to leave the cursor, and it is turned on there: the
    reader is in the middle of a word and needs to see where the next letter
    lands.
    """
    if not rows:
        return NOTHING
    #  Hidden while the rows paint, for the reason every whole frame hides it:
    #  a cursor left on trails across what is being drawn. A block is smaller
    #  than a frame and no less visible, being the part of the screen the
    #  reader is watching. The caret turns it back on at the end.
    out = bytearray([ScreenControl.CURSOR_OFF])
    at = 0
    wrapped = False
    #  Explicitly, rather than by asking whether anything has been written:
    #  something has, the cursor having just been hidden.
    started = False
    for row in rows:
        if not started:
            out += to_row(row)
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
        started = True
        at = row
    if caret is not None:
        out += caret_bytes(*caret)
    return bytes(out)


def typed_bytes(before: Frame, after: Frame, row: int, *, at: int) -> bytes | None:
    """Return the smallest change turning one row into the other, or None.

    Args:
        before: The frame as the terminal has it.
        after: The frame wanted.
        row: The row that may have changed.
        at: Where the cursor sits, which both cases rely on -- the last repaint
            left it where the next character goes.

    Returns:
        The bytes for one character typed (that character, the cursor advancing
        itself) or one rubbed out (cursor left, a space, cursor left, the space
        taking the row's background). None where the row changed some other way
        or anywhere but under the cursor, and the caller must repaint it whole.
    """
    was, now = _row_of(before, row), _row_of(after, row)
    if was == now:
        return NOTHING
    if not 0 <= at <= COLUMNS:
        return None
    grew = _cells(after, row)[at] != _BLANK and _cells(before, row)[at] == _BLANK
    shrank = _cells(before, row)[at - 1] != _BLANK and _cells(after, row)[at - 1] == _BLANK
    if grew and _same_but_for(before, after, row, at):
        return encode_text(after.text_at(row, at, 1))
    if at > 0 and shrank and _same_but_for(before, after, row, at - 1):
        return bytes(
            [ScreenControl.CURSOR_LEFT, _BLANK, ScreenControl.CURSOR_LEFT]
        )
    return None


def _same_but_for(before: Frame, after: Frame, row: int, column: int) -> bool:
    """Whether two rows differ in exactly one cell, and that one."""
    was, now = _cells(before, row), _cells(after, row)
    return all(
        was[other] == now[other] for other in range(COLUMNS) if other != column
    )


def _cells(frame: Frame, row: int) -> list[int]:
    return [frame.cell(row, column) for column in range(COLUMNS)]


def _row_of(frame: Frame, row: int) -> bytes:
    return bytes(frame.row_bytes(row))


def to_row(row: int) -> bytes:
    """Move the cursor to the start of a row, by the cheapest route.

    Home, then down -- the only positioning viewdata has -- except the last row,
    which home-then-up reaches in two bytes by wrapping off the top. Measured in
    `docs/spikes/spike_cursor_output.py`, not assumed. Shared with the command
    line and the idle-warning bar, which both draw the footer row and so take
    that two-byte route.
    """
    if row == ROWS - 1:
        return bytes([ScreenControl.CURSOR_HOME, ScreenControl.CURSOR_UP])
    return bytes([ScreenControl.CURSOR_HOME]) + bytes([ScreenControl.LINE_FEED]) * row


def caret_bytes(row: int, column: int) -> bytes:
    """Put the cursor at a cell and show it.

    Sent after a whole frame as well as after a repaint: a frame begins by
    hiding the cursor, which is right everywhere except a page with a field on
    it, where a reader needs to see where their typing will go *before* they
    have typed anything.

    Cursor right skips without erasing -- measured -- so walking across a row
    already drawn disturbs nothing. Cheaper than it looks: a field is near the
    top of a frame and the caret near the start of a row.
    """
    if not 0 <= column <= COLUMNS:
        raise ValueError(f"column {column} is not on a {COLUMNS}-column row")
    return (
        to_row(row)
        + bytes([ScreenControl.CURSOR_RIGHT]) * column
        + bytes([ScreenControl.CURSOR_ON])
    )
