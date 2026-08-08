"""Setting a line of text in a mosaic font: where each letter goes.

The result is a bitmap, which `blocks.block_runs` turns into cells and
`Composition` places on a frame. This module knows about letters and spacing
and nothing about attributes.

**Three spacings, and all three are wanted.**

`FIXED` gives every letter the face's design width, putting the ink back where
the designer had it within that -- which is what the glyph's bearing is kept
for. It is what a column of figures wants, and the only one whose arithmetic a
page can do in its head.

`PROPORTIONAL` gives every letter its own advance. A row is 78 blocks wide, and
ten letters at a fixed eight blocks do not fit on one; the same ten set
proportionally do, with room to spare. So this is the default.

`KERNED` lets a pair close up further where their shapes allow it -- the arm of
a `T` over the foot of an `L`. It needs no kerning table: the shapes are in the
bitmaps already, so each pair is fitted by looking at the rows where both have
ink and closing up until the tightest of them reaches the gap. Rows where
either is blank have no say, which is exactly where the space to be had is.

Two things bound that fitting, and both are there to stop it eating what it
should not. A pair may close up by no more than `limit` blocks, and **kerning
does not cross a blank glyph**: a narrow letter after a space would otherwise
slide back into the space and run the words together.

The lettering is trimmed on the right to the last block of ink, because a
banner is centred on what it draws rather than on what it advanced past. The
left is left alone: a leading bearing is the face's own design.
"""

from collections.abc import Sequence
from enum import Enum
from typing import Final

from sextile.viewdata.font import Font, Glyph

#: Blocks that must stay clear between two letters when kerning. One is the
#: least that keeps them legible: at this size a block is a stroke's width.
_GAP: Final = 1

#: The most a kerned pair may close up by.
_LIMIT: Final = 1


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
) -> list[list[bool]]:
    """`text` set in `font`, as rows of blocks, as tall as the face."""
    placed = _placements(text, font, spacing, gap, limit)
    width = _width(placed)
    rows = [[False] * width for _ in range(font.height)]
    for glyph, left in placed:
        for y, row in enumerate(glyph.bitmap):
            for x, block in enumerate(row):
                if block:
                    rows[y][left + x] = True
    return rows


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
