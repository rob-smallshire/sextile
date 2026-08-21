"""Breaking text into lines narrow enough for a viewdata frame.

Forty columns is narrow, and a word that fits no line is split rather than
dropped or allowed to overrun. Widths are counted in cells, not characters,
because transliteration can lengthen a string on its way to the wire -- the G0
set draws `…` as three full stops -- so a line measured in characters can
overrun the row it was wrapped for.

Lines are balanced by default rather than filled greedily: balancing chooses the
breaks that minimise the squared slack, spreading the unavoidable gap across
several lines rather than stranding it on one. `Breaking` says how the slack is
laid out -- `PARAGRAPH` leaves the last line free, since a paragraph's final line
is expected to be short; `DISPLAY` counts it, so a short centred title reads as
two even lines rather than a full one and an orphan.
"""

from enum import Enum

from sextile.viewdata.measure import cell_count

__all__ = [
    "Breaking",
    "wrap_text",
    "wrap_within",
]


class Breaking(Enum):
    """How wrapping lays the unavoidable slack across the lines it breaks into.

    Attributes:
        GREEDY: As much on each line as fits, taken in turn.
        PARAGRAPH: Balanced with the last line free, for body text: a
            paragraph's final line is expected to be short, so the lines before
            it are not crammed to fatten it. The default.
        DISPLAY: Balanced with the last line counted, for a centred or display
            string, so a short two-line title reads as two even lines rather
            than a full first line and an orphan.
    """

    GREEDY = "greedy"
    PARAGRAPH = "paragraph"
    DISPLAY = "display"


def wrap_text(text: str, width: int, *, breaking: Breaking = Breaking.PARAGRAPH) -> list[str]:
    """Break text into lines of at most ``width`` cells.

    Args:
        text: The text to wrap.
        width: The cells a line may take.
        breaking: How to lay the slack across the lines -- `PARAGRAPH` (the
            default) for body text, `DISPLAY` for a centred string, `GREEDY` to
            fill each line in turn. See `Breaking`.

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
    if breaking is Breaking.GREEDY:
        return _greedy(pieces, width)
    return _balanced(pieces, width, count_last=breaking is Breaking.DISPLAY)


def wrap_within(
    text: str, *, cells: int, rows: int, breaking: Breaking = Breaking.PARAGRAPH
) -> list[str]:
    """Wrap text to a region with a height as well as a width, cutting to fit.

    Args:
        text: The text to wrap.
        cells: The cells a line may take.
        rows: The most lines the region holds.
        breaking: How to lay the slack, as `wrap_text` takes it; `DISPLAY` for a
            centred region such as a masthead's description.

    Returns:
        The wrapped lines, at most `rows` of them; the words that do not fit are
        the last ones, so size a region for the longest thing it can be handed.
        Empty for a region with no room, rather than raising, since a squeezed
        layout is a bug to fix and not a reason to fail on a live call.

    Wrapped as usual and cut: balanced wrapping never needs a line a greedy fill
    would have saved, which holds for `DISPLAY` as well as `PARAGRAPH`.
    """
    if rows < 1 or cells < 1:
        return []
    return wrap_text(text, cells, breaking=breaking)[:rows]


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


def _balanced(pieces: list[str], width: int, *, count_last: bool) -> list[str]:
    """The breaks that leave the least squared slack.

    Args:
        pieces: The words, already split so each fits the width.
        width: The cells a line may take.
        count_last: Whether the final line is charged its slack (`DISPLAY`) or
            left free (`PARAGRAPH`).
    """
    count = len(pieces)
    #  cost[i] is the least slack achievable laying out pieces[i:].
    cost = [0.0] + [float("inf")] * count
    cost[count] = 0.0
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
            #  The final line is charged its slack only in display mode; a
            #  paragraph leaves it free, so its earlier lines are not crammed to
            #  fatten a last line nobody minds being short.
            penalty = 0.0 if (last and not count_last) else float(slack * slack)
            here = cost[end + 1] + penalty
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
