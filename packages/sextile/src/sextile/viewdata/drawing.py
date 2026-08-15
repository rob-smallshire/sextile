"""One-call conveniences for putting things on a frame.

There are two writers a page draws through: `Composition`, the declarative one,
which takes a whole row and works the attributes out at once; and `RowWriter`,
the sequential one, which writes a row left to right. These functions are the
small operations every page turns out to want -- centring a heading, ruling a
line, drawing a gauge -- each built once on whichever of the two fits, so there
is one way to do each rather than a twin on every writer.

`centred` and `centred_double` and the rules go through `Composition`, since
centring is accounting about attributes and that is what a composition is for.
`bar` and `key_row` go through `RowWriter`, being a run laid down a cell at a
time. All are free functions rather than methods, so a service can write its own
beside them; they take a canvas and a row, and none of them knows what a page is.

The block characters are how the rules and the gauge are drawn: the G1 set gives
each cell a 2x3 grid of blocks, so a frame is 80x72 addressable points, and
`bar` is the one-dimensional case of plotting into that. The two-dimensional
case -- reading a bitmap into cells and placing it -- is `blocks.py` and
`composition.py`, with `lettering.py` on top for text.
"""

from typing import Final

from sextile.viewdata.canvas import Canvas, RowWriter
from sextile.viewdata.composition import Align, Composition, Style
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.measure import cell_count, fitted

__all__ = [
    "bar",
    "centred",
    "centred_double",
    "key_row",
    "rule",
    "thin_rule",
]

#: The all-lit mosaic as a block pattern, all six blocks set. Every rule and bar
#: is a run of these; encoded for a cell it is 0x7F in the G1 set.
SOLID_BLOCKS: Final = 0b111111

#: The middle row of blocks in a cell, and nothing else: a rule one block thick
#: instead of three. Separated, it is a dotted line rather than a bar.
MIDDLE_BLOCKS: Final = 0b001100

#: A cell for the colour of each of the two columns a key table has.
_COLUMNS: Final = 2

#: A run of mosaic needs a graphics colour, and a separated run needs the
#: separated attribute as well. Both occupy cells.
_CONTIGUOUS_ATTRIBUTES: Final = 1
_SEPARATED_ATTRIBUTES: Final = 2


def centred(
    canvas: Canvas, row: int, text: str, colour: Colour | None = None
) -> None:
    """Write text across the middle of a row.

    Args:
        canvas: The frame to draw on.
        row: The row to write on.
        text: The text, fitted to the row if it is too wide.
        colour: The colour, white by default.

    The middle is the composition's to work out: what a style costs in cells
    decides where the middle is.
    """
    _place(canvas, row, fitted(text, COLUMNS - 1), colour)


def centred_double(
    canvas: Canvas, row: int, text: str, colour: Colour | None = None
) -> None:
    """Write text centred at twice the height, which costs the row below too.

    Args:
        canvas: The frame to draw on.
        row: The top row; the bottom halves are drawn on the row below.
        text: The text, fitted to the row.
        colour: The colour, white by default.
    """
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
    """Draw a rule in separated mosaic graphics across the middle of a row.

    Args:
        canvas: The frame to draw on.
        row: The row to rule.
        colour: The colour, blue by default.

    The widest a rule can be and stay centred is the row less the two attribute
    cells at each end; inset at one end and flush at the other reads as a mistake.
    """
    cells = COLUMNS - 2 * _SEPARATED_ATTRIBUTES
    Composition().blocks(
        row, Align.CENTRE, [SOLID_BLOCKS] * cells, colour, separated=True
    ).draw(canvas)


def key_row(row: "RowWriter", key: str, meaning: str, *, column: int) -> None:
    """Write a key on the left and what it does on the right, in two columns.

    Args:
        row: The row writer to draw on.
        key: The key, in yellow, or empty to indent to the meaning column and
            carry a meaning too long for one row onto the next.
        meaning: What the key does, in white.
        column: The cell the meaning column begins at, given so several frames
            of one table line up.
    """
    if key:
        row.text(fitted(key, column), Colour.YELLOW)
        row.skip(max(column - cell_count(key), 0))
    else:
        row.skip(column + _COLUMNS)
    if meaning:
        row.text(fitted(meaning, COLUMNS - column - _COLUMNS), Colour.WHITE)


def thin_rule(canvas: Canvas, row: int, colour: Colour = Colour.BLUE) -> None:
    """Draw a lighter rule, one block thick, across the middle of a row.

    Args:
        canvas: The frame to draw on.
        row: The row to rule.
        colour: The colour, blue by default.

    A sixth of the ink of `rule`: a bar reads as a page edge, so a divider
    inside a page, between two things that are both content, is drawn lighter.
    """
    cells = COLUMNS - 2 * _SEPARATED_ATTRIBUTES
    Composition().blocks(
        row, Align.CENTRE, [MIDDLE_BLOCKS] * cells, colour, separated=True
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
    """Draw a run of mosaic cells, ``lit`` of them solid and the rest blank.

    Args:
        canvas: The frame to draw on.
        row: The row to draw on.
        colour: The colour of the lit cells.
        column: The cell the run begins at, after its colour attribute.
        cells: How many cells the run has, or the rest of the row from `column`.
        lit: How many are solid, from the left, or all of them.
        separated: Whether the blocks are drawn separated, not contiguous.

    Raises:
        ValueError: If there is no room for the run.

    A rule is the whole run lit; a gauge some of it. Unlit cells are written
    blank, not left alone, so a bar drawn over a longer one shortens rather than
    failing to lengthen.
    """
    attributes = _SEPARATED_ATTRIBUTES if separated else _CONTIGUOUS_ATTRIBUTES
    width = (COLUMNS - column - attributes) if cells is None else cells
    if width <= 0:
        raise ValueError(f"no room for a bar at column {column} of row {row}")
    solid = width if lit is None else max(min(lit, width), 0)
    #  Through the sequential mosaic writer, as the all-lit block and the empty
    #  one -- by pattern rather than by writing a Unicode character and trusting
    #  it to encode to 0x7F. The writer lays the graphics colour (and the
    #  separated attribute if asked) before the blocks, the cells bar reserved.
    patterns = [SOLID_BLOCKS] * solid + [0] * (width - solid)
    canvas.row(row).starting_at(column).mosaic(patterns, colour, separated=separated)
