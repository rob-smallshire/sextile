"""Laying blocks out as frames.

Blocks are flattened into a stream of rendered rows first, then divided
between frames. Doing it in that order keeps the two hard parts apart: deciding what a
quotation four deep should look like, and deciding where a screen ends.

Colour carries structure. Someone reading in monochrome still follows the text;
someone reading in colour can tell at a glance whose words they are looking at.
A quotation is cyan, a listing green, an image or attachment magenta, and the
author's own words white.

A page has frames a-z and no more, so a document long enough to exhaust them says so
rather than ending mid-sentence with nothing to explain it.
"""

from dataclasses import dataclass
from typing import Final

from sextile.addressing import FRAMES_PER_PAGE
from sextile.content.blocks import (
    Attachment,
    Block,
    Code,
    Document,
    Image,
    ListItem,
    Paragraph,
    Quote,
)
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import COLUMNS, ROWS, Frame
from sextile.viewdata.wrapping import wrap_text

#: Rows a frame gives to the content itself, the rest being chrome.
BODY_ROWS: Final = ROWS - 3

#: A page's frames are lettered a-z.
MAX_FRAMES: Final = FRAMES_PER_PAGE

_QUOTE_INDENT: Final = 2

#  Beyond this the indent costs more than it conveys, so deeper quotations stop
#  moving right and rely on colour alone.
_MAX_QUOTE_DEPTH: Final = 4

#: Said on the last frame of anything too long to show in full, by a
#: document and by a template alike: a reader who has reached the end of
#: what there is should not have to wonder whether that was all of it.
TRUNCATION_NOTICE: Final = "... TRUNCATED, TOO LONG TO SHOW"


@dataclass(frozen=True)
class Row:
    """One rendered row of body text, with the colour that says what it is."""

    text: str
    colour: Colour
    indent: int = 0


def rows_for(content: Document) -> list[Row]:
    """Render a document into rows, without dividing them between frames.

    For a caller that wants to do its own pagination -- a template that has a
    lead-in on the first frame, say, and so cannot use a fixed frame size.
    """
    rows = list(_rows_for(content.blocks, depth=0))
    rows.extend(_link_rows(content))
    return rows


def paginate(content: Document, rows_per_frame: int = BODY_ROWS) -> list[list[Row]]:
    """Render a document and divide it into frame-sized groups of rows.

    Stops short of drawing, so a page builder can place these rows beneath its
    own chrome and title block without this module knowing either exists.
    """
    return _divide(rows_for(content), rows_per_frame)


def draw_rows(canvas: Canvas, first_row: int, rows: list[Row]) -> None:
    """Draw rendered rows onto a canvas, starting at a row."""
    for offset, row in enumerate(rows):
        if row.text:
            canvas.row(first_row + offset).skip(row.indent).text(row.text, row.colour)


def lay_out(content: Document) -> list[Frame]:
    """Render a document as bare frames, with no chrome.

    For where the content is the only thing of interest.
    """
    return [_frame_for(page) for page in paginate(content)]


def _rows_for(blocks: tuple[Block, ...], depth: int) -> list[Row]:
    rows: list[Row] = []
    indent = min(depth, _MAX_QUOTE_DEPTH) * _QUOTE_INDENT
    width = COLUMNS - indent - 1  # one cell for the colour attribute
    colour = Colour.CYAN if depth else Colour.WHITE

    for block in blocks:
        if rows:
            rows.append(Row("", colour, indent))
        match block:
            case Paragraph(lines):
                for line in lines:
                    rows.extend(
                        Row(text, colour, indent) for text in wrap_text(line, width)
                    )
            case Quote(inner):
                rows.extend(_rows_for(inner, depth + 1))
            case Code(lines):
                for line in lines:
                    rows.extend(
                        Row(text, Colour.GREEN, indent) for text in wrap_text(line, width)
                    )
            case ListItem(text):
                wrapped = wrap_text(text, width - 2)
                rows.extend(
                    Row(f"{'*' if index == 0 else ' '} {piece}", colour, indent)
                    for index, piece in enumerate(wrapped)
                )
            case Image(description):
                rows.extend(_marked("IMAGE", description, indent, width))
            case Attachment(name):
                rows.extend(_marked("FILE", name, indent, width))

    return _without_leading_blanks(rows)


def _marked(kind: str, what: str, indent: int, width: int) -> list[Row]:
    """A picture or a file, named across as many rows as the name needs.

    These were the two blocks that built a row without wrapping it, so a
    photograph with a long caption overran the frame and raised where every
    other kind of block had been wrapped for years. Real posts carry captions
    like `vlcsnap-2026-08-02-17h29m56s151.png`.
    """
    return [
        Row(text, Colour.MAGENTA, indent)
        for text in wrap_text(f"[{kind}: {what}]", width)
    ]


def _link_rows(content: Document) -> list[Row]:
    if not content.links:
        return []
    rows = [Row("", Colour.WHITE), Row("LINKS", Colour.YELLOW)]
    for link in content.links:
        wrapped = wrap_text(link.url, COLUMNS - 5)
        for index, piece in enumerate(wrapped):
            marker = f"[{link.number}] " if index == 0 else "    "
            rows.append(Row(f"{marker}{piece}", Colour.YELLOW))
    return rows


def _divide(rows: list[Row], rows_per_frame: int) -> list[list[Row]]:
    """Divide rendered rows into frame-sized groups."""
    pages = [
        rows[start : start + rows_per_frame] for start in range(0, len(rows), rows_per_frame)
    ] or [[]]

    if len(pages) > MAX_FRAMES:
        #  A page has frames a-z and no more. Running out must be said, not
        #  silently swallowed.
        pages = pages[:MAX_FRAMES]
        pages[-1] = pages[-1][: rows_per_frame - 1]
        pages[-1].append(Row(TRUNCATION_NOTICE, Colour.RED))

    return pages


def _frame_for(rows: list[Row]) -> Frame:
    canvas = Canvas()
    draw_rows(canvas, 0, rows)
    return canvas.frame


def _without_leading_blanks(rows: list[Row]) -> list[Row]:
    index = 0
    while index < len(rows) and not rows[index].text:
        index += 1
    return rows[index:]
