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
from sextile.viewdata.controls import Colour, Control, graphics_colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS

#: The mosaic character with all six blocks lit. Every rule and bar is a run of
#: these; in the G1 set it is 0x7F.
SOLID: Final = "▮"

#: A run of mosaic needs a graphics colour, and a separated run needs the
#: separated attribute as well. Both occupy cells.
_CONTIGUOUS_ATTRIBUTES: Final = 1
_SEPARATED_ATTRIBUTES: Final = 2


def fitted(text: str, cells: int) -> str:
    """Text shortened until it occupies no more than the cells available.

    Measured in cells rather than characters: transliteration can lengthen a
    string on its way to the wire, so trimming by length would leave something
    that still overruns. There is no ellipsis, because on forty columns three
    dots to say "there was more" cost more than the three characters they hide.
    """
    if cells <= 0:
        return ""
    shortened = text
    while cell_count(shortened) > cells:
        shortened = shortened[:-1]
    return shortened


def centre(width: int, *, room: int = COLUMNS) -> int:
    """The column something `width` cells wide starts at to sit in the middle.

    **One rule, used by everything on a frame that centres itself.** Text,
    rules and lettering made of blocks each used to work this out for
    themselves and came out as much as a cell and a half apart, which on a
    title frame is plainly visible.

    Left-biased where it cannot be exact -- an odd number of spare cells has to
    go somewhere -- and always the same way, so two things centred on the same
    frame are out by at most half a cell and never in opposite directions.
    """
    return max((room - width) // 2, 0)


def centred(
    canvas: Canvas,
    row: int,
    text: str,
    colour: Colour | None = None,
    *,
    width: int = COLUMNS,
) -> None:
    """Write text across the middle of a row.

    The colour attribute is paid for out of the room *before* the text, so the
    text lands in the same cells whether there is one or not.
    """
    attribute = 1 if colour is not None else 0
    shortened = fitted(text, width - attribute)
    start = centre(cell_count(shortened), room=width)
    canvas.row(row).skip(max(start - attribute, 0)).text(shortened, colour)


def centred_double(
    canvas: Canvas, row: int, text: str, colour: Colour | None = None
) -> None:
    """The same at twice the height, which costs the row below as well.

    Two cells go on attributes here -- the double height and the colour -- so
    the room to centre within is two fewer than the row.
    """
    attributes = 1 + (1 if colour is not None else 0)
    shortened = fitted(text, COLUMNS - attributes)
    start = centre(cell_count(shortened))
    canvas.double_height(row, shortened, colour, column=max(start - attributes, 0))


def rule(canvas: Canvas, row: int, colour: Colour = Colour.BLUE) -> None:
    """A rule in separated mosaic graphics, centred on the row.

    A run of blocks cannot begin before the attributes that colour it, so the
    two cells they take on the left are left free on the right as well. A rule
    inset at one end and flush at the other reads as a mistake, and sets a
    different middle from everything else on the frame.
    """
    margin = _SEPARATED_ATTRIBUTES
    bar(canvas, row, colour=colour, separated=True, cells=COLUMNS - 2 * margin)


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
