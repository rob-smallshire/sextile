"""A demonstration frame, built to be looked at.

It exercises the whole frame engine at once -- chrome, colour, mosaic graphics,
wrapped body text, a page number -- so a glance at ``sextile render --demo``
shows whether anything is obviously wrong. Nothing else depends on it.
"""

from sextile.pages.numbering import MainIndex, Post, format_page_number
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour, Control, graphics_colour
from sextile.viewdata.frame import COLUMNS, Frame

SERVICE_NAME = "SEXTILE"

#  A real Stardot post, numbered by the scheme rather than by hand, so the demo
#  cannot drift away from what the parser accepts.
_SAMPLE_PAGE_NUMBER = format_page_number(Post(489493))
_MAIN_INDEX_NUMBER = format_page_number(MainIndex())

_SAMPLE_BODY = (
    "I've been investigating the cycle timing of the Acorn NS32016 second "
    "processor. The board runs at 8MHz nominally, but the Tube interface "
    "introduces wait states that nobody seems to have documented. Has anyone "
    "measured this properly?"
)

#  A solid rule drawn in mosaic graphics: 0x7F is all six blocks set.
_SOLID_MOSAIC = "▮"


def demo_frame() -> Frame:
    """A frame showing everything the engine can currently do."""
    canvas = Canvas()

    _header(canvas, row=0)
    _rule(canvas, row=1, colour=Colour.BLUE)

    canvas.row(3).text("NS32016 TIMING INVESTIGATION", Colour.YELLOW)
    canvas.row(5).text("RobertS", Colour.GREEN).at(30).text("21:20", Colour.GREEN)

    canvas.paragraph(7, 12, _SAMPLE_BODY, colour=Colour.WHITE)

    _rule(canvas, row=21, colour=Colour.BLUE)
    _footer(canvas, row=22)

    return canvas.frame


def _header(canvas: Canvas, row: int) -> None:
    canvas.row(row).text(SERVICE_NAME, Colour.CYAN)
    canvas.right(row, _SAMPLE_PAGE_NUMBER, Colour.WHITE)


def _rule(canvas: Canvas, row: int, colour: Colour) -> None:
    """A full-width rule in separated mosaic graphics."""
    writer = canvas.row(row)
    frame = canvas.frame
    frame.set_attribute(row, 0, graphics_colour(colour))
    frame.set_attribute(row, 1, Control.SEPARATED_GRAPHICS)
    writer.skip(2)
    frame.write(row, 2, _SOLID_MOSAIC * (COLUMNS - 2))


def _footer(canvas: Canvas, row: int) -> None:
    canvas.row(row).text("Key ", Colour.WHITE).text("#", Colour.YELLOW).text(
        " for next frame", Colour.WHITE
    )
    canvas.row(row + 1).text("Key ", Colour.WHITE).text(
        f"*{_MAIN_INDEX_NUMBER}#", Colour.YELLOW
    ).text(" for the main index", Colour.WHITE)
