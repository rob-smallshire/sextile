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
from sextile.viewdata.chrome import FOOTER_ROW
from sextile.viewdata.controls import Colour, Control, alpha_colour
from sextile.viewdata.encoding import ScreenControl, encode_text
from sextile.viewdata.frame import COLUMNS, Frame

CANCEL_HINT: Final = "* cancels"

#  Three cells to say "white on blue": a background can only be taken from a
#  foreground, so the colour must be chosen, made the background, and then the
#  text colour chosen again.
_BUFFER_ATTRIBUTES: Final = 3

#  Two more to return to yellow on black for the hint.
_HINT_ATTRIBUTES: Final = 2

_SPACE: Final = 0x20

#: Cells the typed request has to itself, once the colours and hint are paid for.
BUFFER_CELLS: Final = COLUMNS - _BUFFER_ATTRIBUTES - _HINT_ATTRIBUTES - len(CANCEL_HINT)

def draw_command_line(canvas: Canvas, entry: str) -> None:
    """Draw the command line across the footer row."""
    frame = canvas.frame
    frame.set_attribute(FOOTER_ROW, 0, Control.ALPHA_BLUE)
    frame.set_attribute(FOOTER_ROW, 1, Control.NEW_BACKGROUND)
    frame.set_attribute(FOOTER_ROW, 2, Control.ALPHA_WHITE)

    #  The tail, not the head: what was typed most recently is what a reader is
    #  checking. Real page numbers are far shorter than this anyway.
    shown = entry[-BUFFER_CELLS:]
    frame.write(FOOTER_ROW, _BUFFER_ATTRIBUTES, shown.ljust(BUFFER_CELLS))

    hint_start = _BUFFER_ATTRIBUTES + BUFFER_CELLS
    frame.set_attribute(FOOTER_ROW, hint_start, Control.BLACK_BACKGROUND)
    frame.set_attribute(FOOTER_ROW, hint_start + 1, alpha_colour(Colour.YELLOW))
    frame.write(FOOTER_ROW, hint_start + _HINT_ATTRIBUTES, CANCEL_HINT)


def incremental_bytes(entry: str, displayed: str) -> bytes | None:
    """The smallest change turning what is showing into what is wanted.

    Two cases are worth the trouble, both because the cursor is already in the
    right place. A character typed needs only that character: the cursor
    advances itself. A character rubbed out needs cursor left, a space, and
    cursor left again -- the space inheriting the row's blue background, since
    the attributes that set it sit earlier in the row and are not touched.

    Returns None when the row genuinely has to be redrawn: the line appearing,
    or a buffer wide enough to scroll, where everything on it moves.
    """
    if not displayed:
        return None
    if max(len(entry), len(displayed)) > BUFFER_CELLS:
        return None
    if len(entry) == len(displayed) + 1 and entry.startswith(displayed):
        return encode_text(entry[-1])
    if len(entry) == len(displayed) - 1 and displayed.startswith(entry):
        return bytes(
            [ScreenControl.CURSOR_LEFT, _SPACE, ScreenControl.CURSOR_LEFT]
        )
    return None


def command_line_bytes(entry: str) -> bytes:
    """The bytes that draw the command line, leaving the page beneath alone.

    The cursor is put where the next character will land and turned on, which is
    the one place in the service a cursor tells a reader anything. Getting there
    costs a few cursor-rights: they skip without erasing, so stepping across the
    row already drawn disturbs nothing.
    """
    canvas = Canvas(Frame())
    draw_command_line(canvas, entry)
    shown = entry[-BUFFER_CELLS:]
    return (
        _to_footer_row()
        + canvas.frame.row_bytes(FOOTER_ROW)
        + _to_footer_row()
        + bytes([ScreenControl.CURSOR_RIGHT]) * (_BUFFER_ATTRIBUTES + len(shown))
        + bytes([ScreenControl.CURSOR_ON])
    )


def footer_bytes(frame: Frame) -> bytes:
    """The bytes that put a page's own footer back, after a request is done."""
    return (
        bytes([ScreenControl.CURSOR_OFF])
        + _to_footer_row()
        + frame.row_bytes(FOOTER_ROW)
    )


def _to_footer_row() -> bytes:
    """Home, then up -- which wraps to row 23. Measured, not assumed."""
    return bytes([ScreenControl.CURSOR_HOME, ScreenControl.CURSOR_UP])
