"""Series drawn on the block grid.

A cell is two blocks across and three down, so a region of the frame is a
bitmap: `across = 2 * cells`, `down = 3 * rows`. These turn a run of numbers
into such a bitmap, and `blocks.block_runs` turns that into the mosaic cells a
row writer can place. This module does not decide what is being plotted or what
colour it is drawn in.

**Values arrive as fractions of the height, not as data.** 0.0 is the bottom
row of blocks and 1.0 the top. Deciding what the top and bottom of a chart mean
is the caller's, and it is the whole of the interesting part: whether a scale
starts at zero, whether it is fixed so that two frames can be compared, where a
threshold falls.

**A value sits at the middle of its share of the width**, so that a chart lines
up with a column of labels or pictures above it. That leaves half a share blank
at each end, which the line fills by running level out to the edges: it is the
last thing known, and a line that stopped short would read as data that stopped.
"""

from collections.abc import Sequence

__all__ = [
    "bars",
    "curve",
]


def curve(
    fractions: Sequence[float | None], *, across: int, down: int
) -> list[list[bool]]:
    """Draw a line through evenly spaced values as a bitmap.

    Args:
        fractions: The values, each a fraction of the height from 0.0 to 1.0,
            or None for a gap that breaks the line rather than being crossed.
        across: The bitmap's width in blocks.
        down: The bitmap's height in blocks.

    Returns:
        A `down` by `across` grid of lit blocks. One block to a column, so the
        line joins corner to corner and reads as a line rather than a filled
        wall. A missing value breaks it: joining across a gap would draw a
        claim about a point the series says nothing about.
    """
    grid = [[False] * across for _ in range(down)]
    if not fractions or across < 1 or down < 1:
        return grid
    heights = [None if value is None else _height(value, down) for value in fractions]
    for column in range(across):
        here = _sampled(heights, column, across)
        if here is not None:
            grid[down - 1 - here][column] = True
    return grid


def bars(
    fractions: Sequence[float | None], *, across: int, down: int
) -> list[list[bool]]:
    """Columns standing on the bottom of the region, one to a value.

    Each takes its whole share of the width, so the bars touch. That suits a
    series that is a quantity per interval rather than a level at an instant --
    there is no gap between one interval and the next.
    """
    grid = [[False] * across for _ in range(down)]
    if not fractions or across < 1 or down < 1:
        return grid
    for column in range(across):
        value = fractions[min(column * len(fractions) // across, len(fractions) - 1)]
        if value is None:
            continue
        for level in range(round(max(value, 0.0) * down)):
            grid[down - 1 - level][column] = True
    return grid


def _sampled(heights: Sequence[int | None], column: int, across: int) -> int | None:
    """The height of the line at one column of blocks.

    Level before the first value and after the last, and straight between two.
    """
    count = len(heights)
    share = across / count
    #  Where each value sits: the middle of its share of the width.
    at = [share * (index + 0.5) for index in range(count)]
    if column <= at[0]:
        return heights[0]
    if column >= at[-1]:
        return heights[-1]
    for index in range(count - 1):
        if at[index] <= column <= at[index + 1]:
            before, after = heights[index], heights[index + 1]
            if before is None or after is None:
                return None
            across_here = at[index + 1] - at[index]
            along = (column - at[index]) / across_here
            return round(before + (after - before) * along)
    return None


def _height(fraction: float, down: int) -> int:
    """A fraction of the height, as the block row it lands on."""
    return max(0, min(down - 1, round(fraction * (down - 1))))

