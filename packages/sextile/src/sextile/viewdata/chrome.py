"""The furniture every frame carries.

Four of the twenty-four rows go to chrome: a header naming the page and giving
its number, a rule beneath it, a rule above the footer, and the footer's
navigation prompt. Twenty rows remain, and that is the budget every page builder
works to.

The header is where a reader looks to know where they are and what to quote to
come back, so the page number is placed first and the title is given whatever
room is left. Titles reach forty characters unaided, so one that would crowd
the number is truncated rather than allowed to push it away.

The title is whatever the service says it is, including nothing. There is no
default: a framework that wrote its own name across the top of somebody else's
service would be naming the machinery rather than the thing being read.
"""

from typing import Final

from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import rule
from sextile.viewdata.encoding import cell_count, fitted
from sextile.viewdata.frame import COLUMNS, ROWS

HEADER_ROW: Final = 0
_TOP_RULE_ROW: Final = 1
CONTENT_FIRST_ROW: Final = 2
CONTENT_ROWS: Final = 20
_BOTTOM_RULE_ROW: Final = ROWS - 2
FOOTER_ROW: Final = ROWS - 1

#  A colour attribute costs a cell, and the header carries two runs.
_HEADER_ATTRIBUTES: Final = 2
_GAP: Final = 1


def draw_chrome(canvas: Canvas, *, title: str, page_number: str, prompt: str) -> None:
    """Draw the header, the rules and the footer, leaving the content rows alone."""
    _draw_header(canvas, title, page_number)
    rule(canvas, _TOP_RULE_ROW)
    rule(canvas, _BOTTOM_RULE_ROW)
    _draw_footer(canvas, prompt)


def _draw_header(canvas: Canvas, title: str, page_number: str) -> None:
    #  Not everything drawn is a page. A notice given in reply to a keypress has
    #  no number of its own, and the title may have the whole row.
    if not page_number:
        canvas.row(HEADER_ROW).text(fitted(title, COLUMNS - 1), Colour.CYAN)
        return
    number_cells = cell_count(page_number)
    available = COLUMNS - number_cells - _HEADER_ATTRIBUTES - _GAP
    canvas.row(HEADER_ROW).text(fitted(title, available), Colour.CYAN)
    canvas.right(HEADER_ROW, page_number, Colour.WHITE)


def _draw_footer(canvas: Canvas, prompt: str) -> None:
    if prompt:
        canvas.row(FOOTER_ROW).text(fitted(prompt, COLUMNS - 1), Colour.YELLOW)
