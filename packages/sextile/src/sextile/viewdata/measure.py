"""How many cells text takes on the wire, and fitting it to a width.

Arithmetic about cells, and nothing about bytes: a caller laying out a row asks
these rather than counting characters, because transliteration on the way to the
wire changes the count -- an ellipsis becomes three characters and an accented
letter one. Kept apart from the drawing helpers because everything that lays out
a row needs it, `RowWriter` included, and `RowWriter` is what the drawing
helpers are built on and so cannot import from. It draws only on `encoding` to
measure, and `encoding` draws on nothing here, so there is no cycle either way.
"""

from sextile.viewdata.encoding import encode_text

__all__ = [
    "cell_count",
    "fitted",
]


def cell_count(text: str) -> int:
    """How many cells text occupies once transliterated.

    Not the same as its length: an ellipsis becomes three characters and an
    accented letter one, so callers laying out a row must ask rather than assume.
    """
    return len(encode_text(text))


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
