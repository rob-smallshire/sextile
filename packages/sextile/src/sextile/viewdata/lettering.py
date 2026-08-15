"""Setting a line of text in a mosaic font: where each letter goes.

The result is a bitmap, which `blocks.block_runs` turns into cells and
`Composition` places on a frame. This module knows about letters and spacing and
nothing about attributes: `cells` takes a string to mosaic patterns, and `place`
and `boxed` add it to a `Composition`.

Three spacings, chosen with `Spacing`. `FIXED` gives every letter the face's
design width, which a column of figures wants. `PROPORTIONAL` gives each its own
advance and is the default, since a row of 78 blocks does not hold ten letters
at a fixed eight. `KERNED` closes a pair up further where their bitmaps allow --
by no more than `limit` blocks, and never across a blank glyph, or a letter
after a space would slide back and run the words together.

The lettering is trimmed on the right to the last block of ink, because a
banner is centred on what it draws rather than on what it advanced past. The
left is left alone: a leading bearing is the face's own design.
"""

from collections.abc import Sequence
from enum import Enum
from typing import Final

from sextile.viewdata.blocks import BLOCKS_ACROSS, BLOCKS_DOWN, block_runs
from sextile.viewdata.composition import (
    Align,
    Composition,
    DoesNotFit,
    Panel,
    Where,
)
from sextile.viewdata.controls import Colour
from sextile.viewdata.font import Font, Glyph

__all__ = [
    "Spacing",
    "boxed",
    "cells_needed",
    "place",
    "rows_needed",
    "width",
]

#: Blocks that must stay clear between two letters when kerning. One is the
#: least that keeps them legible: at this size a block is a stroke's width.
_GAP: Final = 1

#: The most a kerned pair may close up by.
_LIMIT: Final = 1

#: A panel's own first cell carries the attribute that colours it, so a box
#: fitted round something is one cell wider than its padding asks for.
_ATTRIBUTE: Final = 1


class Spacing(Enum):
    """How far apart the letters go."""

    FIXED = "fixed"
    PROPORTIONAL = "proportional"
    KERNED = "kerned"


def bitmap(
    text: str,
    font: Font,
    *,
    spacing: Spacing = Spacing.PROPORTIONAL,
    gap: int = _GAP,
    limit: int = _LIMIT,
    trim: bool = True,
) -> list[list[bool]]:
    """`text` set in `font`, as rows of blocks, as tall as the ink.

    A face leaves room for descenders and accents whether a line uses them or
    not, and three blank block-rows is a whole row of a screen that has
    twenty-four -- so the blank rows above and below the line go, as the blank
    columns after it do. `trim=False` keeps the face's full height, which is
    what two lines that must share a baseline want.
    """
    placed = _placements(text, font, spacing, gap, limit)
    width = _width(placed)
    rows = [[False] * width for _ in range(font.height)]
    for glyph, left in placed:
        for y, row in enumerate(glyph.bitmap):
            for x, block in enumerate(row):
                if block:
                    rows[y][left + x] = True
    return _trimmed(rows) if trim else rows


def _trimmed(rows: list[list[bool]]) -> list[list[bool]]:
    """The line with its blank rows taken off the top and the bottom.

    A line with no ink at all is left as it is: it is a gap of the face's
    height, and a gap of no height is not what anybody asked for.
    """
    inked = [index for index, row in enumerate(rows) if any(row)]
    return rows[inked[0] : inked[-1] + 1] if inked else rows


def width(
    text: str,
    font: Font,
    *,
    spacing: Spacing = Spacing.PROPORTIONAL,
    gap: int = _GAP,
    limit: int = _LIMIT,
) -> int:
    """How many blocks `text` would take, without setting it."""
    return _width(_placements(text, font, spacing, gap, limit))


def _width(placed: Sequence[tuple[Glyph, int]]) -> int:
    return max((left + glyph.width for glyph, left in placed), default=0)


def _placements(
    text: str, font: Font, spacing: Spacing, gap: int, limit: int
) -> list[tuple[Glyph, int]]:
    """Each glyph and the column its picture starts at."""
    if spacing not in Spacing:
        raise ValueError(f"{spacing!r} is not a spacing")
    placed: list[tuple[Glyph, int]] = []
    pen = 0
    for character in text:
        glyph = font.glyph(character)
        if spacing is Spacing.FIXED:
            placed.append((glyph, pen + glyph.bearing))
            pen += font.fixed
            continue
        left = pen
        if spacing is Spacing.KERNED and _kernable(placed, glyph):
            left = max(_closest(placed[-1], glyph, gap), pen - limit)
        placed.append((glyph, left))
        pen = left + glyph.advance
    return placed


def _kernable(placed: Sequence[tuple[Glyph, int]], glyph: Glyph) -> bool:
    """Whether this pair is one that may be fitted at all.

    Nothing to fit against, nothing to fit, or a blank between the two: in each
    case the letter goes where the advance put it. The blank is the important
    one -- it is what keeps a word from closing up over the space before it.
    """
    return bool(placed) and _inked(placed[-1][0]) and _inked(glyph)


def _inked(glyph: Glyph) -> bool:
    return any(any(row) for row in glyph.bitmap)


def _closest(previous: tuple[Glyph, int], glyph: Glyph, gap: int) -> int:
    """The leftmost column this glyph may start at without crowding the last.

    Considered a row at a time: on each row where both have ink there must be
    `gap` clear blocks between the last block of one and the first of the
    other. A row where either is blank cannot bring them into contact and so
    has no say, which is where a kerned pair finds its room. The result can be
    further right than the advance would have put it, for a face whose glyphs
    are wider than they advance; a letter is never pushed into the one before.
    """
    before, at = previous
    return max(
        (
            at + right + 1 + gap - left
            for right, left in zip(_right(before), _left(glyph), strict=True)
            if right is not None and left is not None
        ),
        default=0,
    )


def _right(glyph: Glyph) -> list[int | None]:
    """The last lit block on each row, or None for a row with no ink."""
    return [
        max((x for x, block in enumerate(row) if block), default=None)
        for row in glyph.bitmap
    ]


def _left(glyph: Glyph) -> list[int | None]:
    return [
        min((x for x, block in enumerate(row) if block), default=None)
        for row in glyph.bitmap
    ]


def cells(
    text: str,
    font: Font,
    *,
    spacing: Spacing = Spacing.PROPORTIONAL,
    gap: int = _GAP,
    limit: int = _LIMIT,
    inverted: bool = False,
    margin: int = 0,
    trim: bool = True,
) -> list[list[int]]:
    """`text` set in `font` as mosaic patterns, a list of them for each cell row.

    `margin` widens the field by that many blocks on every side, which is what
    an inverted banner wants: the letters are holes in a lit field, and without
    a margin the field ends where the ink does and the letters touch its edge.

    **The line sits in the middle of the rows it takes.** A cell is three
    blocks deep and a line of letters is rarely a multiple of three, so there
    is slack; leaving all of it under the letters puts them at the top of their
    rows, which shows the moment anything is drawn behind them.
    """
    picture = bitmap(text, font, spacing=spacing, gap=gap, limit=limit, trim=trim)
    return block_runs(_settled(_bordered(picture, margin)), inverted=inverted)


def _settled(picture: list[list[bool]]) -> list[list[bool]]:
    """The picture padded to whole rows of cells, the slack shared top and bottom."""
    width = len(picture[0]) if picture else 0
    slack = -len(picture) % BLOCKS_DOWN
    above = slack // 2
    blank = [[False] * width]
    return blank * above + picture + blank * (slack - above)


def _bordered(picture: list[list[bool]], margin: int) -> list[list[bool]]:
    if not margin:
        return picture
    width = (len(picture[0]) if picture else 0) + 2 * margin
    blank = [[False] * width for _ in range(margin)]
    return blank + [[False] * margin + row + [False] * margin for row in picture] + blank


def place(
    composition: Composition,
    row: Where,
    text: str,
    font: Font,
    colour: Colour = Colour.WHITE,
    *,
    column: int | None = None,
    within: Panel | None = None,
    spacing: Spacing = Spacing.PROPORTIONAL,
    gap: int = _GAP,
    limit: int = _LIMIT,
    inverted: bool = False,
    margin: int = 0,
    trim: bool = True,
    separated: bool = False,
) -> Composition:
    """Add `text`, set in `font`, to a composition with its top row at `row`.

    `row` may be an alignment as well, which centres the letters down the panel
    they are going on -- to the block, so a line that does not fill its rows
    sits in the middle of them rather than at the top.

    Centred unless a column is given -- within `within`, if it is going on a
    panel, so that a word in a coloured box is centred in the box. The
    composition works out where that leaves it, accounting for what the colour
    attribute costs and how far into a cell the ink may start; this module
    handles the letters.
    """
    return composition.picture(
        row,
        column if column is not None else Align.CENTRE,
        cells(
            text,
            font,
            spacing=spacing,
            gap=gap,
            limit=limit,
            inverted=inverted,
            margin=margin,
            trim=trim,
        ),
        colour,
        within=within,
        separated=separated,
    )


def boxed(
    composition: Composition,
    row: Where,
    text: str,
    font: Font,
    colour: Colour = Colour.WHITE,
    background: Colour = Colour.BLUE,
    *,
    where: Where = Align.CENTRE,
    padding: int = 1,
    rows: int | None = None,
    spacing: Spacing = Spacing.PROPORTIONAL,
    gap: int = _GAP,
    limit: int = _LIMIT,
    trim: bool = True,
) -> Panel:
    """Set lettering in a coloured box fitted around it.

    Args:
        composition: The composition to add the box and the letters to.
        row: The top row of the box, or an alignment to centre it down the
            frame.
        text: The word to set.
        font: The face to set it in.
        colour: The letters.
        background: The field they sit in.
        where: Where the box goes across the frame.
        padding: Cells of colour either side of the letters.
        rows: How tall the box is, in rows. The height of the letters unless
            given.
        spacing: How far apart the letters go.
        gap: Blocks that must stay clear between two letters when kerning.
        limit: The most a kerned pair may close up by.
        trim: Whether to cut the face to its own ink rather than keeping its
            full height.

    Returns:
        The box, so that a caller may place something else against it.

    Raises:
        DoesNotFit: If `rows` is fewer than the letters need. A box shorter
            than its letters is a stripe behind them rather than a box, and is
            drawn as two things: a panel from `Composition.panel` and the
            letters from `place`, both centred, the composition working out
            that the row they share is coloured.

    The Ceefax effect: a word in a field of colour, cyan on blue or red on
    yellow. The box is fitted here, where the letters can be measured, rather
    than by a caller counting them -- it takes one cell on its left for the
    attribute that colours it, which is the sort of arithmetic a caller gets
    wrong. The letters are centred in it both ways, to the block.
    """
    if rows is not None and rows < len(cells(text, font, spacing=spacing, trim=trim)):
        raise DoesNotFit(
            f"a box of {rows} row(s) is shorter than the letters it is to hold; "
            f"for a stripe behind them, draw a panel and the lettering separately"
        )
    patterns = cells(text, font, spacing=spacing, gap=gap, limit=limit, trim=trim)
    deep = len(patterns)
    tall = rows if rows is not None else deep
    first, letters = _rows_of(row, deep, tall)
    panel = composition.panel(
        first,
        where,
        width=len(patterns[0]) + 2 * padding + _ATTRIBUTE,
        colour=background,
        rows=tall,
    )
    composition.picture(letters, Align.CENTRE, patterns, colour, within=panel)
    return panel


def _rows_of(row: Where, deep: int, tall: int) -> tuple[Where, Where]:
    """Where the box starts and where the letters do, given a row for one.

    A box that holds the letters grows around them, upwards as well as down, so
    they stay near the row asked for -- except at the top of the frame, where
    there is nowhere above to grow into.
    """
    if not isinstance(row, int):
        return row, Align.CENTRE
    above = (tall - deep) // 2
    return max(row - above, 0), max(row - above, 0) + above


def cells_needed(
    text: str,
    font: Font,
    *,
    spacing: Spacing = Spacing.PROPORTIONAL,
    gap: int = _GAP,
    limit: int = _LIMIT,
    padding: int = 0,
) -> int:
    """Measure how many cells a line of lettering would take across.

    Args:
        text: The line to measure. It is not set, only measured.
        font: The face it would be set in.
        spacing: How far apart the letters would go.
        gap: Blocks that must stay clear between two letters when kerning.
        limit: The most a kerned pair may close up by.
        padding: Cells of margin to count either side of the letters, for a
            caller sizing a box round them rather than the letters alone.

    Returns:
        The width in cells, rounded up: a line ending part way into a cell
        still occupies the whole of it.

    The companion of `rows_needed`, and what a page needs to draw a stripe behind
    a word without drawing the word first: a panel of this width and the
    lettering, both centred, line up without either knowing about the other.
    """
    across = width(text, font, spacing=spacing, gap=gap, limit=limit)
    return -(-across // BLOCKS_ACROSS) + 2 * padding


def rows_needed(font: Font, *, margin: int = 0) -> int:
    """How many rows of the frame a face needs at most, with `margin` of border.

    The most, not the number a given line takes: a line of capitals is trimmed
    to its own ink and may come out shorter.
    """
    return -(-(font.height + 2 * margin) // BLOCKS_DOWN)
