"""The warning that a silent line is about to be released.

A caller reading one frame for ten minutes has no way of knowing the service is
about to ring off, and being cut off without warning is not distinguishable from
a fault. So after a period of silence the footer row becomes a bar that drains,
with an instruction; the next key dismisses it. It covers a part-keyed request,
which the parser holds and gives back the moment the reader touches anything.

Drawn over that row alone, never the frame, and only when what it would say has
changed. The whole row is redrawn each time rather than the one cell the bar
gave up: the wire has no absolute cursor addressing, so reaching the cell to
change costs about as much as the row. The bar is mosaic graphics rather than
punctuation so it reads as a quantity at a glance.
"""

from typing import Final

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.command_line import footer_bytes
from sextile.viewdata.controls import Colour, alpha_colour
from sextile.viewdata.drawing import bar
from sextile.viewdata.frame import COLUMNS, FOOTER_ROW, Frame

#: What a reader has to do about it. Deliberately not naming a particular key:
#: while this is showing, the first key does this and nothing else.
RESUME_HINT: Final = "Press a key"

_HINT_COLUMN: Final = 1
_GAP: Final = 2

#: Where the bar's own colour attribute sits, the bar beginning after it.
_BAR_ATTRIBUTE_COLUMN: Final = _HINT_COLUMN + len(RESUME_HINT) + _GAP

#: Cells the bar has, once the two attributes and the hint are paid for.
BAR_CELLS: Final = COLUMNS - _BAR_ATTRIBUTE_COLUMN - 1

#: Below this much of the time remaining, the warning turns red.
_URGENT: Final = 0.25


def lit_cells(remaining: float) -> int:
    """Return how many bar cells are lit for the fraction of time remaining.

    Args:
        remaining: The fraction of the warning period left, 1.0 to 0.0.

    Returns:
        Cells lit, rounded up while any time is left so an emptied bar means the
        line has gone rather than that it is about to.
    """
    fraction = min(max(remaining, 0.0), 1.0)
    if fraction <= 0.0:
        return 0
    return max(1, round(fraction * BAR_CELLS))


def idle_warning_bytes(remaining: float) -> bytes:
    """Draw the warning bar and return its bytes, leaving the page beneath alone.

    Args:
        remaining: The fraction of the warning period left, which sets how much
            of the bar is lit and turns it red near the end.

    Returns:
        The bytes that redraw the footer row as the bar.
    """
    colour = Colour.RED if remaining <= _URGENT else Colour.YELLOW
    canvas = Canvas(Frame())
    frame = canvas.frame
    frame.set_attribute(FOOTER_ROW, 0, alpha_colour(colour))
    frame.write(FOOTER_ROW, _HINT_COLUMN, RESUME_HINT)
    #  The whole bar is written, lit and unlit alike: the row is redrawn in
    #  place, so a cell the bar has given up has to be overwritten rather than
    #  left showing what it said before. `bar` does that.
    bar(
        canvas,
        FOOTER_ROW,
        colour=colour,
        column=_BAR_ATTRIBUTE_COLUMN,
        cells=BAR_CELLS,
        lit=lit_cells(remaining),
    )
    #  The same as putting a page's footer back: hide the cursor, reach row 23,
    #  send it. The bar is what this frame's row 23 holds rather than a prompt.
    return footer_bytes(frame)
