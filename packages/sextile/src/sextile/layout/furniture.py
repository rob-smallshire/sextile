"""The fixed bands round a page's content: title, rules, and the prompt.

Furniture is drawn in the second pass that builds a page, once the frame count
is known, docked to the top or the foot of every frame. A furnishing claims no
keys of its own: what a footer names belongs to the layout or to the parts, and
it is handed the assembled list rather than composing one.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from typing import Final, Protocol, runtime_checkable

from sextile.layout.footer import FOOTER_WIDTH, FooterItem, render_footer
from sextile.page import PageAddress
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import rule
from sextile.viewdata.encoding import cell_count, fitted
from sextile.viewdata.frame import COLUMNS, ROWS


class Edge(Enum):
    """Which end of a frame a furnishing is docked to."""

    TOP = auto()
    BOTTOM = auto()


@dataclass(frozen=True)
class FrameContext:
    """What a furnishing is told about the frame it is drawing on.

    Attributes:
        title: What the page is called.
        address: The address the page answers to, or None where it has no
            number of its own to show.
        index: Which frame this is, counting from nought.
        frames: How many frames the page came to.
        offered: Every key that works on this frame, in the order the prompt
            should try to name them: what the parts claimed, then the
            shortcuts, the movement keys, and the way home.
    """

    title: str
    address: PageAddress | None
    index: int
    frames: int
    offered: Sequence[FooterItem]
    numbered: bool = True

    @property
    def page_number(self) -> str:
        """The page number as this frame displays it, or empty for none."""
        if self.address is None or not self.numbered:
            return ""
        return self.address.frame_number(self.index)


@runtime_checkable
class Furnishing(Protocol):
    """A band docked to the top or the foot of every frame.

    A furnishing claims no keys. What it names belongs to the layout or to the
    parts, and it is handed the assembled list rather than composing one.
    """

    @property
    def edge(self) -> Edge:
        """Which end of the frame this is docked to."""
        ...

    @property
    def rows(self) -> int:
        """How many rows it takes, on every frame."""
        ...

    def draw(self, canvas: Canvas, at: int, page: FrameContext) -> None:
        """Draw this band in the rows the layout has reserved for it."""
        ...


@dataclass(frozen=True)
class Header:
    """The page title, and the page number at the right of the same row."""

    colour: Colour = Colour.CYAN
    numbered: Colour = Colour.WHITE
    edge: Edge = Edge.TOP
    rows: int = 1

    #: A colour attribute costs a cell, and this row carries two runs.
    _ATTRIBUTES: Final = 2
    _GAP: Final = 1

    def draw(self, canvas: Canvas, at: int, page: FrameContext) -> None:
        #  Not everything drawn is a page a reader could have keyed. A notice
        #  answering a number that names nothing has none to show, and the
        #  title may have the whole row.
        if not page.page_number:
            canvas.row(at).text(fitted(page.title, COLUMNS - 1), self.colour)
            return
        spare = COLUMNS - cell_count(page.page_number) - self._ATTRIBUTES - self._GAP
        canvas.row(at).text(fitted(page.title, spare), self.colour)
        canvas.right(at, page.page_number, self.numbered)


@dataclass(frozen=True)
class Rule:
    """A rule across the middle of a row, dividing the content from the rest."""

    edge: Edge = Edge.TOP
    colour: Colour = Colour.BLUE
    rows: int = 1

    def draw(self, canvas: Canvas, at: int, page: FrameContext) -> None:
        del page  # a rule says nothing about the page it is on
        rule(canvas, at, self.colour)


@dataclass(frozen=True)
class Footer:
    """Every key that works on this frame, and what each of them does."""

    colour: Colour = Colour.YELLOW
    edge: Edge = Edge.BOTTOM
    rows: int = 1

    def draw(self, canvas: Canvas, at: int, page: FrameContext) -> None:
        said = render_footer(page.offered, FOOTER_WIDTH)
        if said:
            canvas.row(at).text(fitted(said, COLUMNS - 1), self.colour)


#: What a page is furnished with unless a service or a page says otherwise: a
#: title above a rule, and a rule above the keys. Two levels of override, and
#: no cascade -- a site is one thing and a page that does something
#: irreversible may say so, but a reader learns where the page number sits once.
DEFAULT_FURNITURE: Final[tuple[Furnishing, ...]] = (
    Header(),
    Rule(edge=Edge.TOP),
    Rule(edge=Edge.BOTTOM),
    Footer(),
)


def content_rows(furniture: Sequence[Furnishing]) -> range:
    """Which rows of a frame are left for the content.

    Args:
        furniture: The bands docked to the frame, in the order they are drawn
            down it.

    Returns:
        The rows between them, which is the whole frame where there is no
        furniture at all.
    """
    above = sum(one.rows for one in furniture if one.edge is Edge.TOP)
    below = sum(one.rows for one in furniture if one.edge is Edge.BOTTOM)
    return range(above, ROWS - below)
