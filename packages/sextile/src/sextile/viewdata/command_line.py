"""The command line a reader types a page request into.

Commstar does not echo `*123#` -- confirmed by watching a tcpser trace while
typing one -- so unless Sextile draws it, a reader cannot see what they have
typed. It replaces the footer while a request is being entered, which makes the
mode change visible and gives `**` somewhere to be explained; there is nowhere
in the ordinary footer to say so.

Drawn over the footer row alone, not by redrawing the frame. `CURSOR_HOME` then
cursor up wraps to row 23, measured in `docs/spikes/spike_cursor_output.py`, so
the whole thing costs about fifty bytes: a few milliseconds at 9600 baud, and
under half a second even at 1200. That is what makes it affordable on every
keystroke.

The row reads as a field: white on blue for what has been typed, then yellow on
black for the reminder that `*` cancels.
"""

from typing import Final

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Attribute, Colour, alpha_colour
from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import COLUMNS, FOOTER_ROW, Frame
from sextile.viewdata.repaint import to_row, typed_bytes

CANCEL_HINT: Final = "* cancels"

#  Three cells to say "white on blue": a background can only be taken from a
#  foreground, so the colour must be chosen, made the background, and then the
#  text colour chosen again.
_BUFFER_ATTRIBUTES: Final = 3

#  Two more to return to yellow on black for the hint.
_HINT_ATTRIBUTES: Final = 2

#: Cells the typed request has to itself, once the colours and hint are paid for.
BUFFER_CELLS: Final = COLUMNS - _BUFFER_ATTRIBUTES - _HINT_ATTRIBUTES - len(CANCEL_HINT)

def draw_command_line(canvas: Canvas, entry: str) -> None:
    """Draw the command line across the footer row."""
    frame = canvas.frame
    frame.set_attribute(FOOTER_ROW, 0, Attribute.ALPHA_BLUE)
    frame.set_attribute(FOOTER_ROW, 1, Attribute.NEW_BACKGROUND)
    frame.set_attribute(FOOTER_ROW, 2, Attribute.ALPHA_WHITE)

    #  The tail, not the head: what was typed most recently is what a reader is
    #  checking. Real page numbers are far shorter than this anyway.
    shown = entry[-BUFFER_CELLS:]
    frame.write(FOOTER_ROW, _BUFFER_ATTRIBUTES, shown.ljust(BUFFER_CELLS))

    hint_start = _BUFFER_ATTRIBUTES + BUFFER_CELLS
    frame.set_attribute(FOOTER_ROW, hint_start, Attribute.BLACK_BACKGROUND)
    frame.set_attribute(FOOTER_ROW, hint_start + 1, alpha_colour(Colour.YELLOW))
    frame.write(FOOTER_ROW, hint_start + _HINT_ATTRIBUTES, CANCEL_HINT)


def incremental_bytes(entry: str, displayed: str) -> bytes | None:
    """The smallest change turning what is showing into what is wanted.

    The command line is one row of a frame, so this is `repaint.typed_bytes`
    over two of them: the row as it stands and the row wanted. A character typed
    costs that character, the cursor advancing itself; one rubbed out costs
    cursor left, a space and cursor left again, the space inheriting the row's
    blue background. The cursor is where the last draw left it, at the end of
    what was displayed.

    Returns None when the row has to be redrawn whole: the line appearing, or a
    buffer wide enough to scroll, where everything on it moves.
    """
    if not displayed:
        return None
    if max(len(entry), len(displayed)) > BUFFER_CELLS:
        return None
    return typed_bytes(
        _command_line_frame(displayed),
        _command_line_frame(entry),
        FOOTER_ROW,
        at=_BUFFER_ATTRIBUTES + len(displayed),
    )


def _command_line_frame(entry: str) -> Frame:
    """A blank frame with the command line for `entry` drawn across its foot."""
    frame = Frame()
    draw_command_line(Canvas(frame), entry)
    return frame


def command_line_bytes(entry: str) -> bytes:
    """Draw the command line and return its bytes, leaving the page beneath alone.

    Args:
        entry: What the reader has keyed of a request so far.

    Returns:
        The bytes that redraw the footer row as the command line, with the
        cursor put where the next character will land and turned on. Getting
        there costs a few cursor-rights, which skip without erasing.
    """
    canvas = Canvas(Frame())
    draw_command_line(canvas, entry)
    shown = entry[-BUFFER_CELLS:]
    return (
        to_row(FOOTER_ROW)
        + canvas.frame.row_bytes(FOOTER_ROW)
        + to_row(FOOTER_ROW)
        + bytes([ScreenControl.CURSOR_RIGHT]) * (_BUFFER_ATTRIBUTES + len(shown))
        + bytes([ScreenControl.CURSOR_ON])
    )


def footer_bytes(frame: Frame) -> bytes:
    """Send the footer row of a frame, cursor hidden, leaving the rest alone.

    Puts a page's own footer back after a request is done, and is what the
    idle-warning bar sends too: both draw only row 23 and reach it the same way.
    """
    return (
        bytes([ScreenControl.CURSOR_OFF])
        + to_row(FOOTER_ROW)
        + frame.row_bytes(FOOTER_ROW)
    )
