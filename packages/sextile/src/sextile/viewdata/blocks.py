"""Turning a picture into the blocks a frame can draw.

**A small picture is written in the source as the picture it is**, which is
what `icon` is for: an arrow, a symbol, a rule end, anything a page wants that
the character set has not got. Six-bit patterns typed as numbers are write-only,
and a picture drawn in a comment beside them is a copy that goes stale.

    ARROW = icon(\"\"\"
           #
            #
        ######
            #
           #
    \"\"\")


A mosaic cell is a 2x3 grid of blocks, so a frame is 80x72 of them -- 78 in
practice, an attribute cell going on the left of each row a picture spans. This
turns a bitmap into the six-bit patterns those cells carry.

**Inverted is the interesting case, and it is how teletext has always done dark
lettering.** The SAA5050 has no alpha-black attribute: the colour codes run
0x01-0x07 and there is no way to ask for a black foreground. So a Ceefax banner
of black letters on cyan is not black letters at all -- it is a solid cyan field
with letter-shaped holes in it, the unlit blocks showing the default black
background through. It costs one graphics attribute on each row and no
background attributes whatever, which is cheaper than the coloured-background
version it appears to be.

That is why `inverted` belongs here rather than in whatever draws the letters:
inverting a glyph on its own would leave the space around it black. What has to
be inverted is the whole field the picture occupies.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from textwrap import dedent
from typing import Final

__all__ = [
    "BLOCKS_ACROSS",
    "BLOCKS_DOWN",
    "Icon",
    "block_runs",
    "icon",
    "read_bitmap",
]

#: Block positions within a cell, from the least significant bit up. Read from
#: Beebium's `get_graphics_row`; `charset.mosaic_code` turns them into a byte.
_BLOCK_BITS: Final = ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2))

#: A cell is two blocks across and three down.
BLOCKS_ACROSS: Final = 2
BLOCKS_DOWN: Final = 3


def read_bitmap(rows: Sequence[str], lit: str = "#") -> list[list[bool]]:
    """Read a picture written out as characters, one character to a block.

    Args:
        rows: The picture, a string a row. They need not be the same length:
            a short one is taken as ending in blanks.
        lit: Which characters mean a block that is on. Any character in this
            string counts, so a picture may be drawn in more than one mark
            where that makes it easier to read.

    Returns:
        The picture as rows of blocks, for `block_runs` to pack into the
        six-bit cell patterns a frame carries.

    Example:
        A picture is legible in the source it is written in::

            read_bitmap([
                "  ##  ",
                " #### ",
                "######",
            ])
    """
    return [[character in lit for character in row] for row in rows]


def block_runs(
    bitmap: Sequence[Sequence[bool]], *, inverted: bool = False
) -> list[list[int]]:
    """A bitmap as six-bit cell patterns, a list of them for each row of cells.

    The picture is padded out to whole cells: to a multiple of two blocks across
    and three down. Padding is dark in the ordinary case and lit when inverted,
    so that an inverted picture is a solid field rather than a solid field with
    a ragged edge.
    """
    height = len(bitmap)
    width = max((len(row) for row in bitmap), default=0)
    cells_across = -(-width // BLOCKS_ACROSS)
    cells_down = -(-height // BLOCKS_DOWN)

    def block(x: int, y: int) -> bool:
        on = y < height and x < len(bitmap[y]) and bool(bitmap[y][x])
        return not on if inverted else on

    return [
        [
            sum(
                1 << index
                for index, (dx, dy) in enumerate(_BLOCK_BITS)
                if block(cell * BLOCKS_ACROSS + dx, row * BLOCKS_DOWN + dy)
            )
            for cell in range(cells_across)
        ]
        for row in range(cells_down)
    ]


#: Within a cell's six bits, the three blocks down its left-hand side and the
#: three down its right. See `_BLOCK_BITS`: the two alternate.
LEFT_BLOCKS: Final = 0b010101
RIGHT_BLOCKS: Final = 0b101010


def shifted(patterns: Sequence[int]) -> list[int]:
    """The same run of cells with its picture one block to the right.

    Half a cell, in other words -- which is the finest a mosaic picture can be
    positioned, and the difference between a banner that is centred and one
    that is three quarters of a cell off. Each cell takes the right-hand
    column of the cell before it and its own left-hand column moves right; the
    run grows by a cell if anything falls off the end.
    """
    shifted = [
        ((before & RIGHT_BLOCKS) >> 1) | ((pattern & LEFT_BLOCKS) << 1)
        for before, pattern in zip([0, *patterns], patterns, strict=False)
    ]
    last = (patterns[-1] & RIGHT_BLOCKS) >> 1 if patterns else 0
    return [*shifted, last] if last else shifted


#: The two block rows a cell can shift down into, and the one that falls out of
#: the bottom of it into the cell below.
_UPPER_BLOCKS: Final = 0b001111
_LOWER_BLOCKS: Final = 0b110000


def lowered(rows: Sequence[Sequence[int]], by: int) -> list[list[int]]:
    """A picture moved down by `by` blocks, a third of a cell at a time.

    The vertical counterpart of `shifted`, and finer: a cell is three blocks
    deep, so a picture can be positioned to a third of a row. What falls out of
    the bottom of a cell lands in the top of the one below, and the picture
    grows a row if anything falls out of the last of them.
    """
    picture = [list(patterns) for patterns in rows]
    for _ in range(by):
        picture = _lowered(picture)
    return picture


def _lowered(rows: Sequence[Sequence[int]]) -> list[list[int]]:
    width = max((len(patterns) for patterns in rows), default=0)
    lowered: list[list[int]] = []
    carried = [0] * width
    for patterns in rows:
        padded = list(patterns) + [0] * (width - len(patterns))
        lowered.append(
            [
                ((pattern & _UPPER_BLOCKS) << 2) | carry
                for pattern, carry in zip(padded, carried, strict=True)
            ]
        )
        carried = [(pattern & _LOWER_BLOCKS) >> 4 for pattern in padded]
    return [*lowered, carried] if any(carried) else lowered


@dataclass(frozen=True)
class Icon:
    """A small picture on the block grid, drawn in the source as itself."""

    bitmap: tuple[tuple[bool, ...], ...]

    @property
    def across(self) -> int:
        """Blocks wide."""
        return len(self.bitmap[0]) if self.bitmap else 0

    @property
    def down(self) -> int:
        """Blocks tall."""
        return len(self.bitmap)

    @property
    def cells_across(self) -> int:
        return -(-self.across // BLOCKS_ACROSS)

    @property
    def rows(self) -> int:
        """Rows of the frame it takes."""
        return -(-self.down // BLOCKS_DOWN)

    def turned(self, quarters: int = 1) -> "Icon":
        """A quarter turn anticlockwise, `quarters` times.

        Which is how a set of four arrows is one arrow: the blocks that make a
        diagonal lying down make the same diagonal standing up, corner to
        corner, that being the only diagonal a block grid has.
        """
        turned = self
        for _ in range(quarters % 4):
            turned = Icon(
                bitmap=tuple(
                    tuple(row[turned.across - 1 - column] for row in turned.bitmap)
                    for column in range(turned.across)
                )
            )
        return turned

    def cells(self, *, inverted: bool = False) -> list[list[int]]:
        """The mosaic patterns for it, ready for `Composition.picture`."""
        return block_runs(self.bitmap, inverted=inverted)


def icon(art: str, *, lit: str = "#") -> Icon:
    """A picture written out as itself, indented to suit the code around it.

    Blank lines at either end go, and so does the indentation the source needed
    -- the common part of it, so what one row is drawn further along than
    another survives. Anything that is not `lit` is a block that is off, so a
    picture reads whether it is drawn in dots or in spaces.
    """
    lines = dedent(art.strip("\n")).splitlines()
    return Icon(bitmap=tuple(tuple(block for block in row) for row in _lit(lines, lit)))


def _lit(lines: Sequence[str], lit: str) -> list[list[bool]]:
    width = max((len(line) for line in lines), default=0)
    return [
        [index < len(line) and line[index] in lit for index in range(width)]
        for line in lines
    ]
