"""Free functions for putting things on a frame.

`Canvas` knows how to write a row and what an attribute costs. These are the
next layer up: the small operations every page turns out to want, which had
otherwise been written four times each -- fitting text to the room available,
ruling a line, centring a heading.

Free functions rather than methods, so that a service can write its own beside
them and reach for either without minding which is which. They take a canvas
and a row, and none of them knows what a page is.

This is where the mosaic graphics work belongs when it comes. The block
characters are already how the rules and the countdown bar are drawn: the G1
set gives each cell a 2x3 grid of blocks, so a frame is 80x72 addressable
points, and plotting into that is a matter of setting bits in the right cell.
`bar` is the one-dimensional case of it.
"""

from typing import Final

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.composition import Align, Composition, Style
from sextile.viewdata.controls import Colour, Control, graphics_colour
from sextile.viewdata.encoding import fitted
from sextile.viewdata.frame import COLUMNS

#: The mosaic character with all six blocks lit. Every rule and bar is a run of
#: these; in the G1 set it is 0x7F.
SOLID: Final = "▮"

#: The same as a block pattern, for a composition rather than a row writer.
SOLID_BLOCKS: Final = 0b111111

#: A run of mosaic needs a graphics colour, and a separated run needs the
#: separated attribute as well. Both occupy cells.
_CONTIGUOUS_ATTRIBUTES: Final = 1
_SEPARATED_ATTRIBUTES: Final = 2


def centred(
    canvas: Canvas, row: int, text: str, colour: Colour | None = None
) -> None:
    """Write text across the middle of a row.

    The middle is the composition's to work out, here and in `centred_double`
    and `rule`: what a style costs in cells decides where the middle is, and
    that is its accounting rather than this module's.
    """
    _place(canvas, row, fitted(text, COLUMNS - 1), colour)


def centred_double(
    canvas: Canvas, row: int, text: str, colour: Colour | None = None
) -> None:
    """The same at twice the height, which costs the row below as well."""
    _place(canvas, row, fitted(text, COLUMNS - 2), colour, double_height=True)


def _place(
    canvas: Canvas,
    row: int,
    text: str,
    colour: Colour | None,
    *,
    double_height: bool = False,
) -> None:
    style = Style(
        colour=colour if colour is not None else Colour.WHITE,
        double_height=double_height,
    )
    Composition().text(row, Align.CENTRE, text, style=style).draw(canvas)


def rule(canvas: Canvas, row: int, colour: Colour = Colour.BLUE) -> None:
    """A rule in separated mosaic graphics, across the middle of a row.

    A run of blocks cannot begin before the attributes that colour it, so the
    widest a rule can be *and be centred* is the row less those two cells at
    each end. A rule inset at one end and flush at the other reads as a
    mistake, and sets a different middle from everything else on the frame.
    """
    cells = COLUMNS - 2 * _SEPARATED_ATTRIBUTES
    Composition().blocks(
        row, Align.CENTRE, [SOLID_BLOCKS] * cells, colour, separated=True
    ).draw(canvas)


def bar(
    canvas: Canvas,
    row: int,
    *,
    colour: Colour,
    column: int = 0,
    cells: int | None = None,
    lit: int | None = None,
    separated: bool = False,
) -> None:
    """A run of mosaic cells, ``lit`` of them solid and the rest blank.

    A rule is the whole run lit; a gauge is some of it. Unlit cells are written
    as spaces rather than left alone, so that a bar drawn over one already on
    screen shortens rather than merely failing to lengthen.
    """
    frame = canvas.frame
    attributes = _SEPARATED_ATTRIBUTES if separated else _CONTIGUOUS_ATTRIBUTES
    room = (COLUMNS - column - attributes) if cells is None else cells
    if room <= 0:
        raise ValueError(f"no room for a bar at column {column} of row {row}")
    frame.set_attribute(row, column, graphics_colour(colour))
    if separated:
        frame.set_attribute(row, column + 1, Control.SEPARATED_GRAPHICS)
    solid = room if lit is None else max(min(lit, room), 0)
    frame.write(row, column + attributes, SOLID * solid + " " * (room - solid))
