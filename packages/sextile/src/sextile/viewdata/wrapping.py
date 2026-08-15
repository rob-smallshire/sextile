"""Breaking text into lines narrow enough for a viewdata frame.

Forty columns is narrow, and a word that fits no line is split rather than
dropped or allowed to overrun. Widths are counted in cells, not characters,
because transliteration can lengthen a string on its way to the wire -- the G0
set draws `…` as three full stops -- so a line measured in characters can
overrun the row it was wrapped for.

Lines are balanced by default rather than filled greedily: balancing chooses the
breaks that minimise the squared slack over the paragraph, spreading the
unavoidable gap across several lines rather than stranding it on one. The last
line is free, since a paragraph's final line is expected to be short.
"""

from typing import Final

from sextile.viewdata.measure import cell_count

__all__ = [
    "wrap_text",
    "wrap_within",
]

#: What a line that ends a paragraph costs, however much room is left on it.
_LAST_LINE: Final = 0.0


def wrap_text(text: str, width: int, *, balanced: bool = True) -> list[str]:
    """Break text into lines of at most ``width`` cells.

    Args:
        text: The text to wrap.
        width: The cells a line may take.
        balanced: Whether to spread the slack across the lines (the default) or
            fill each line greedily in turn.

    Returns:
        The lines. Whitespace collapses to single spaces, no line carries
        leading or trailing space, and a word wider than `width` is split
        across as many lines as it needs.

    Raises:
        ValueError: If `width` is less than one.
    """
    if width < 1:
        raise ValueError(f"width must be at least 1, got {width}")

    pieces = [piece for word in text.split() for piece in _fit(word, width)]
    if not pieces:
        return []
    return _balanced(pieces, width) if balanced else _greedy(pieces, width)


def wrap_within(text: str, *, cells: int, rows: int) -> list[str]:
    """Wrap text to a region with a height as well as a width, cutting to fit.

    Args:
        text: The text to wrap.
        cells: The cells a line may take.
        rows: The most lines the region holds.

    Returns:
        The wrapped lines, at most `rows` of them; the words that do not fit are
        the last ones, so size a region for the longest thing it can be handed.
        Empty for a region with no room, rather than raising, since a squeezed
        layout is a bug to fix and not a reason to fail on a live call.

    Wrapped as usual and cut: balanced wrapping never needs a line a greedy fill
    would have saved, which follows from the last line being free.
    """
    if rows < 1 or cells < 1:
        return []
    return wrap_text(text, cells)[:rows]


def _greedy(pieces: list[str], width: int) -> list[str]:
    """As much on each line as will fit, taking them in turn."""
    lines: list[str] = []
    current = ""
    for piece in pieces:
        if not current:
            current = piece
        elif cell_count(current) + 1 + cell_count(piece) <= width:
            current = f"{current} {piece}"
        else:
            lines.append(current)
            current = piece
    if current:
        lines.append(current)
    return lines


def _balanced(pieces: list[str], width: int) -> list[str]:
    """The breaks that leave the least squared slack over the paragraph."""
    count = len(pieces)
    #  cost[i] is the least slack achievable laying out pieces[i:].
    cost = [0.0] + [float("inf")] * count
    cost[count] = _LAST_LINE
    #  Where the line beginning at i is best broken.
    following = list(range(1, count + 2))
    for start in reversed(range(count)):
        cost[start] = float("inf")
        length = -1
        for end in range(start, count):
            length += cell_count(pieces[end]) + 1
            if length > width:
                #  Every line from here on is longer still.
                break
            slack = width - length
            last = end == count - 1
            here = cost[end + 1] + (_LAST_LINE if last else float(slack * slack))
            if here < cost[start]:
                cost[start] = here
                following[start] = end + 1
    lines = []
    start = 0
    while start < count:
        end = following[start]
        lines.append(" ".join(pieces[start:end]))
        start = end
    return lines


def _fit(word: str, width: int) -> list[str]:
    """A word, split into pieces that each fit the width.

    Counted in cells, so a word of characters that widen is split sooner than
    its length suggests.
    """
    if cell_count(word) <= width:
        return [word]
    pieces: list[str] = []
    current = ""
    for character in word:
        if cell_count(current) + cell_count(character) > width:
            pieces.append(current)
            current = ""
        current += character
    if current:
        pieces.append(current)
    return pieces
