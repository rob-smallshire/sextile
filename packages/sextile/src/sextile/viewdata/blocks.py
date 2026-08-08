"""Turning a picture into the blocks a frame can draw.

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
from typing import Final

#: Block positions within a cell, from the least significant bit up. Read from
#: Beebium's `get_graphics_row`; `charset.mosaic_code` turns them into a byte.
_BLOCK_BITS: Final = ((0, 0), (1, 0), (0, 1), (1, 1), (0, 2), (1, 2))

#: A cell is two blocks across and three down.
BLOCKS_ACROSS: Final = 2
BLOCKS_DOWN: Final = 3


def read_bitmap(rows: Sequence[str], lit: str = "#") -> list[list[bool]]:
    """A picture written out as characters, one per block.

    Anything matching ``lit`` is a block that is on. Rows need not be the same
    length; the short ones are taken as ending in blanks.
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
