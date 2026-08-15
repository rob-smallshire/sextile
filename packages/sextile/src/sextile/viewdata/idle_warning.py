"""The warning that a silent line is about to be released.

A caller who has been reading one frame for ten minutes has no way of knowing
the service is about to ring off. Being disconnected without warning, on a
service that answers slowly by design, is indistinguishable from a fault -- and
the remedy, pressing something, is not one a reader can guess at.

So after a period of silence the footer row becomes a bar that drains, with an
instruction. It covers whatever else wanted that row, a part-keyed request
included: what was keyed is held in the parser rather than on the screen, and
comes back the moment the reader touches anything.

Drawn over that row alone, as the command line is -- never the frame -- and only
when what it would say has changed: twenty-five cells over several minutes
changes about twice a minute, and the row costs 45 bytes, a third of a second at
1200 baud.

The whole row goes each time, rather than only the cell the bar has given up.
There is no absolute cursor addressing on the wire: reaching column *c* of row
23 costs `2 + c` bytes of `HOME`, `UP` and
`RIGHT`. Blanking one cell at the right-hand end of a full bar therefore costs
42 bytes against the row's 45, and only becomes worthwhile as the bar empties
and the cell to change moves leftward. Three bytes is not worth a second way of
drawing this.

The bar is mosaic graphics rather than punctuation because it has to read as a
quantity at a glance from across a room, which `======----` does not.
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
    """How much of the bar is still lit, for a fraction of the time remaining.

    Rounded up while any time is left, so that a bar which has emptied means the
    line has gone rather than merely that it is about to.
    """
    fraction = min(max(remaining, 0.0), 1.0)
    if fraction <= 0.0:
        return 0
    return max(1, round(fraction * BAR_CELLS))


def idle_warning_bytes(remaining: float) -> bytes:
    """The bytes that draw the warning, leaving the page beneath alone."""
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
