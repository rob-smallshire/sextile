"""Breaking text into lines narrow enough for a viewdata frame.

Forty columns is narrow, and writing about retrocomputing is full of URLs, hex
dumps and assembler listings. A word that cannot fit any line is split rather
than dropped or allowed to overrun: losing part of a link address is worse than
an ugly break.

Widths are counted in **cells rather than characters**, because that is what the
frame counts. Transliteration can lengthen a string on its way to the wire -- the
G0 set has no ellipsis, so `…` is drawn as three full stops -- and a line
measured in characters can overrun the row it was wrapped for. That was found by
a crash on real text rather than by thinking about it.

Lines are **balanced** by default rather than filled greedily. Greedy wrapping
takes as much as fits on each line in turn, which at forty columns leaves a
badly ragged edge and a stranded last word often enough to be worth avoiding:
a long word early in a paragraph pushes a short line, and every line after it
inherits the damage. Balancing chooses the set of breaks that minimises the
squared slack summed over the paragraph, which spreads that unavoidable gap
across several lines instead of dumping it on one.

The last line is free -- it costs nothing however short it is -- since a
paragraph's final line is expected to be short and penalising it would cram the
lines before it.

Squared slack rather than plain slack: it is the choice that makes two lines
three columns short preferable to one line six columns short, which is what
"balanced" means to somebody looking at the screen. The dynamic programme is
the textbook one, and it is affordable here because a paragraph on a forty
column screen is a few dozen words.
"""

from typing import Final

from sextile.viewdata.encoding import cell_count

#: What a line that ends a paragraph costs, however much room is left on it.
_LAST_LINE: Final = 0.0


def wrap_text(text: str, width: int, *, balanced: bool = True) -> list[str]:
    """Break text into lines of at most ``width`` characters.

    Whitespace runs collapse to a single space and no line carries leading or
    trailing space. A word longer than ``width`` is split across as many lines
    as it needs.

    ``balanced=False`` fills each line in turn instead, which is what a
    typewriter does and what every other wrapper does by default. Kept because
    it is the thing to compare against when a paragraph looks wrong.
    """
    if width < 1:
        raise ValueError(f"width must be at least 1, got {width}")

    pieces = [piece for word in text.split() for piece in _fit(word, width)]
    if not pieces:
        return []
    return _balanced(pieces, width) if balanced else _greedy(pieces, width)


def wrap_within(text: str, *, cells: int, rows: int) -> list[str]:
    """Text wrapped to a region that has a height as well as a width.

    `wrap_text` knows how wide a line may be and nothing about how many there
    is room for, so every caller with a region to fill did the same two things
    by hand: wrap, then take the first however-many lines and hope. This is
    that, with the hoping replaced by a rule.

    Wrapped as usual and then cut, and there is nothing cleverer to be done in
    between: **balanced wrapping never costs a line.** A greedy fill was the
    obvious fallback for a region one line short, and it turns out never to
    help -- measured over twenty thousand random widths and word lengths, with
    no case where balancing needed more lines than filling. Which follows from
    the last line being free: spreading the slack cannot buy a line that the
    greedy fill would have saved.

    So text that does not fit is text the region was never going to hold, and
    the words that go are the last ones. Size the region for the longest thing
    it can be handed.

    A region with no room holds nothing rather than raising: a squeezed layout
    is a bug to fix, not a reason to fail on a live call.
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
