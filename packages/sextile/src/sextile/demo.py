"""A demonstration frame, built to be looked at.

It exercises the whole frame engine at once -- chrome, colour, mosaic graphics,
wrapped body text, a page number -- so a glance at ``sextile render --demo``
shows whether anything is obviously wrong. Nothing else depends on it.
"""

from sextile.addressing import PageAddress, keyed
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import rule
from sextile.viewdata.frame import Frame

SERVICE_NAME = "SEXTILE"

#  Numbers from no particular service: this is a picture of a page rather than
#  a page, and the framework has no numbering of its own to borrow.
_SAMPLE_PAGE_NUMBER = PageAddress("82489493")
_MAIN_INDEX_NUMBER = PageAddress("1")

_SAMPLE_BODY = (
    "I've been investigating the cycle timing of the Acorn NS32016 second "
    "processor. The board runs at 8MHz nominally, but the Tube interface "
    "introduces wait states that nobody seems to have documented. Has anyone "
    "measured this properly?"
)


def demo_frame() -> Frame:
    """A frame showing everything the engine can currently do."""
    canvas = Canvas()

    _header(canvas, row=0)
    rule(canvas, 1)

    canvas.row(3).text("NS32016 TIMING INVESTIGATION", Colour.YELLOW)
    canvas.row(5).text("RobertS", Colour.GREEN).at(30).text("21:20", Colour.GREEN)

    canvas.paragraph(7, 12, _SAMPLE_BODY, colour=Colour.WHITE)

    rule(canvas, 21)
    _footer(canvas, row=22)

    return canvas.frame


def _header(canvas: Canvas, row: int) -> None:
    canvas.row(row).text(SERVICE_NAME, Colour.CYAN)
    canvas.right(row, str(_SAMPLE_PAGE_NUMBER), Colour.WHITE)


def _footer(canvas: Canvas, row: int) -> None:
    canvas.row(row).text("Key ", Colour.WHITE).text("#", Colour.YELLOW).text(
        " for next frame", Colour.WHITE
    )
    canvas.row(row + 1).text("Key ", Colour.WHITE).text(
        keyed(_MAIN_INDEX_NUMBER), Colour.YELLOW
    ).text(" for the main index", Colour.WHITE)
