"""Parts laid out down the frames of a page.

A page's content is a short list of parts. Each is drawn once, drawn on every
frame, or broken across as many frames as it takes, and the order of the list
settles what sits above what. `fill` walks them and returns as many frames as
they needed, which is the first of the two passes that build a page: nothing
here knows how many frames there will be, and nothing here draws furniture.

See [design.md](../../docs/design.md#laying-out-a-page) for the design this
implements and the reasoning behind it.

Example:
    A lead-in on the first frame, a heading on all of them, and a menu that
    goes on for as long as it goes on::

        fill(
            [Once(preamble), Every(headings), Flowing(Menu(items))],
            content_rows(DEFAULT_FURNITURE),
        )
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from sextile.addressing import FRAMES_PER_PAGE, PageAddress
from sextile.keys import (
    ARROW_FOR,
    NEXT_FRAME,
    PREVIOUS_FRAME,
    arrows_lead_where,
    moving,
)
from sextile.page import Page, PageFrame
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import rule
from sextile.viewdata.encoding import cell_count, fitted
from sextile.viewdata.footer import ROOM, FooterItem, Priority, movement, render_footer
from sextile.viewdata.frame import COLUMNS, ROWS
from sextile.viewdata.typesetting import TRUNCATION_NOTICE

if TYPE_CHECKING:
    from sextile.forms import Form


@dataclass(frozen=True)
class Room:
    """What is left of a frame when a part is asked to draw on it.

    Attributes:
        first_row: The row the part would begin on.
        rows: How many rows are left, which may be nought.
        choices: How many of the digits `1-9` are still unclaimed on this
            frame. A reader chooses with one keypress, so this is a budget the
            whole frame shares however it is divided between parts.
    """

    first_row: int
    rows: int
    choices: int


@dataclass(frozen=True)
class Offer:
    """What a part claims on the frame it has drawn on.

    Attributes:
        choices: Keys that lead somewhere, which for a menu are its digits and
            differ from frame to frame.
        named: What to name in the prompt, such as `1-9 select`. The layout
            adds the shortcuts, the movement keys and the way home.
        form: A field the reader types into, where this part is one.
    """

    choices: Mapping[str, PageAddress] = field(default_factory=dict)
    named: Sequence[FooterItem] = ()
    form: "Form | None" = None

    def and_then(self, other: "Offer") -> "Offer":
        """This offer and another, as one.

        Args:
            other: What a later part on the same frame claimed.

        Returns:
            The two merged. Where both claim the same key the later wins,
            which cannot arise between the digits of two flowing parts because
            the second is given only the choices the first left.

        Raises:
            ValueError: If both carry a form. A frame has one field to type
                into; `forms.Fields` is what composes several into one.
        """
        if self.form is not None and other.form is not None:
            raise ValueError("a frame can carry only one form")
        return Offer(
            choices={**self.choices, **other.choices},
            named=[*self.named, *other.named],
            form=self.form or other.form,
        )


@dataclass(frozen=True)
class Placement:
    """What placing a part on one frame came to.

    Attributes:
        rows: The rows it used, which is nought where it would not begin here.
        offer: What it claims on this frame.
        rest: What is left of it for the next frame, or None where it is
            finished. A part that returns nought rows and itself is asking for
            a frame of its own.
    """

    rows: int
    offer: Offer = Offer()
    rest: "Part | None" = None


@runtime_checkable
class Part(Protocol):
    """Something drawn between the rules.

    A part is a description rather than a position, so placing one does not
    change it and a layout may be built more than once. The exception is a
    form, which holds what has been typed.
    """

    def place(self, canvas: Canvas, room: Room) -> Placement:
        """Draw as much as `room` allows, and say what is left over.

        Args:
            canvas: The frame being filled.
            room: What the frame has left to give.

        Returns:
            The rows used, what they claim, and whatever remains for the next
            frame. Returning nought rows and `self` asks for a fresh frame,
            which is how a part too tall for what is left declines to be
            split.
        """
        ...


#: The key that leads home, on every frame of every page that offers one.
HOME_KEY: Final = "0"


@dataclass(frozen=True)
class Shortcut:
    """A key offered on every frame of a page, always leading to one address.

    Attributes:
        key: The character the reader presses, such as `*` or `R`.
        destination: The address that key leads to, from every frame.
        says: How the footer names the key. Put the short form first: the
            footer sheds words from the end when a row is tight, so
            `"index, or key another page"` degrades to `"index"` and then to
            the bare key.
        arrow: Whether the matching cursor key leads there as well. Only `W`,
            `A`, `S` and `D` have one; asking on any other key adds nothing
            rather than raising.
        priority: How hard the footer tries to keep it. A key that is the
            point of the page outranks one that is a convenience.

    A page's digits belong to its entries and change from frame to frame, but a
    shortcut is fixed. It is for the way out that is not the way home: a
    forecast returning to the search that found it, a post returning to the
    board it was on.
    """

    key: str
    destination: PageAddress
    says: str = ""
    #  Not assumed, because whether an arrow means what its letter means
    #  depends on what is on the frame: on a page with a coordinate field it
    #  does not, `W` being West and `S` South.
    arrow: bool = False
    priority: Priority = Priority.PRIMARY


@dataclass(frozen=True)
class Drawn:
    """A part of a stated height, drawn cell by cell by the page itself.

    A picture is positioned at a cell and may be several rows tall, which suits
    a strip of mosaics or a grid of figures and does not suit a line of text.

    Attributes:
        rows: How many rows of the frame it occupies.
        draw: Called with the canvas and the row it begins on.

    Example:
        A month as a grid of weeks, which is the whole of a page's content::

            Once(Drawn(rows=1 + len(weeks), draw=lambda canvas, row: ...))
    """

    rows: int
    draw: "Callable[[Canvas, int], None]"

    def place(self, canvas: Canvas, room: Room) -> Placement:
        if room.rows < self.rows:
            return Placement(rows=0, rest=self)
        self.draw(canvas, room.first_row)
        return Placement(rows=self.rows)


@dataclass(frozen=True)
class Once:
    """A part drawn one time, at its place in the order.

    On the first frame where nothing flowing comes before it, and otherwise on
    whichever frame the flow before it finished on.
    """

    part: Part


@dataclass(frozen=True)
class Every:
    """A part drawn on every frame, at its place in the order.

    Where it comes after any flowing part, its rows are kept back at the foot
    of every frame before that part is asked for its, since a flowing part
    takes the rows left to it and nothing after one would be drawn at all.
    Where it comes before them all, it is drawn where it stands. Several of
    either follow one another in the order the list gives them.
    """

    part: Part


@dataclass(frozen=True)
class Flowing:
    """A part broken across as many frames as it takes.

    Several may appear in one list, and they follow one another: the second
    begins in the row after the first has finished, on whatever frame that is.
    """

    part: Part


@dataclass(frozen=True)
class Break:
    """A division the page means, rather than one the rows forced.

    Whatever follows begins on a new frame. A break that would divide nothing
    is ignored: one at either end of the list, two together, or one on a frame
    with nothing yet drawn on it.
    """


#: One item of a page's content: a part, and which frames it appears on.
type Laid = Once | Every | Flowing | Break


@dataclass
class Filled:
    """One frame's content, before any furniture is drawn on it.

    Attributes:
        canvas: The frame, with the content drawn and the furniture rows left
            alone.
        offer: Everything the parts on this frame claimed, merged.
    """

    canvas: Canvas
    offer: Offer = field(default_factory=Offer)


#: The four letters that move about, which are the ones an arrow stands for.
_MOVEMENT_LETTERS: Final = frozenset(ARROW_FOR)

#: The digits a frame can offer, a reader choosing with one keypress. Held here
#: rather than in the templates because it is a fact about the keypad and the
#: whole frame shares it, however many parts divide it up.
CHOICES_PER_FRAME = 9


def fill(parts: Sequence[Laid], rows: range) -> list[Filled]:
    """Draw the parts onto as many frames as they take.

    Args:
        parts: The page's content, in the order it is to appear.
        rows: The rows of a frame the content may use, the furniture having
            taken the rest.

    Returns:
        One `Filled` a frame, in order, and never none: a page that answered
        with no frames could not be shown. Stops at `FRAMES_PER_PAGE`, a page
        having frames `a` to `z` and no more, and says so on the last row of
        the last of them rather than ending without explanation.

    Raises:
        ValueError: If a part can never be placed, being taller than a whole
            frame, or if two parts on one frame both carry a form.
    """
    state = _State(parts)
    frames: list[Filled] = []
    while True:
        frames.append(_frame(state, rows))
        if state.finished:
            return frames
        if len(frames) == FRAMES_PER_PAGE:
            #  A page has frames a to z and no more. A reader who has reached
            #  the end of what there is should not be left wondering whether
            #  that was all of it, so the last row says what happened.
            frames[-1].canvas.row(rows.stop - 1).text(TRUNCATION_NOTICE, Colour.RED)
            return frames


@dataclass
class _State:
    """How far through the list the filling has got.

    `pending` is what is left to draw of each item, by its position in the
    list: a `Once` that has been drawn and a `Flowing` that has run out are
    both absent from it.
    """

    parts: Sequence[Laid]
    pending: dict[int, Part] = field(default_factory=dict)
    broken: set[int] = field(default_factory=set)
    at_foot: dict[int, Part] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.pending = {
            index: laid.part
            for index, laid in enumerate(self.parts)
            if not isinstance(laid, Break)
        }
        self.at_foot = _at_foot(self.parts)

    @property
    def finished(self) -> bool:
        """Whether anything is left that is not drawn on every frame."""
        return not any(
            index in self.pending
            for index, laid in enumerate(self.parts)
            if not isinstance(laid, Every | Break)
        )


def _at_foot(parts: Sequence[Laid]) -> dict[int, Part]:
    """Which parts drawn on every frame have their rows kept back at the foot.

    Those that come after the first flowing part, in the order the list gives
    them. A flowing part takes the rows left to it, so anything after one that
    waited its turn would find them gone -- and would not merely be pushed
    down, but never drawn at all, since the frame ends when a flowing part
    still has more to give.

    Those before the first flowing part need none of this. Nothing above them
    can take their rows, so they are drawn where they stand.
    """
    flowing = next(
        (index for index, laid in enumerate(parts) if isinstance(laid, Flowing)),
        len(parts),
    )
    return {
        index: laid.part
        for index, laid in enumerate(parts)
        if index > flowing and isinstance(laid, Every)
    }


def _height(part: Part, rows: range) -> int:
    """How many rows a part takes on a whole frame.

    Measured by placing it on a canvas that is then thrown away. A part is a
    description and placing one does not change it, so the second placing --
    the one that counts -- draws the same thing in the row it belongs on. The
    alternative was a second method on every part, asked before every draw.
    """
    return part.place(
        Canvas(), Room(rows.start, len(rows), CHOICES_PER_FRAME)
    ).rows


def _frame(state: _State, rows: range) -> Filled:
    """Fill one frame, taking as much of what is pending as will go on it."""
    filled = Filled(canvas=Canvas())
    #  A part at the end of the list that is drawn on every frame is charged
    #  its rows before anything flowing is asked for its, or the flow takes
    #  them and the note beneath it is written over.
    reserved = _reserved(state, rows)
    at, left = rows.start, len(rows) - reserved
    choices = CHOICES_PER_FRAME
    drawn = False

    for index, laid in enumerate(state.parts):
        if isinstance(laid, Break):
            #  A break on a frame with nothing on it yet would make an empty
            #  one, and a break already honoured is not a second division.
            if drawn and index not in state.broken:
                state.broken.add(index)
                break
            continue
        if index in state.at_foot:
            continue
        part = state.pending.get(index)
        if part is None:
            continue
        placed = part.place(filled.canvas, Room(at, left, choices))
        if placed.rows == 0 and placed.rest is part:
            if not drawn:
                raise ValueError(f"{part!r} can never be placed: it is taller than a frame")
            break
        drawn = True
        filled.offer = filled.offer.and_then(placed.offer)
        at, left = at + placed.rows, left - placed.rows
        choices -= len(placed.offer.choices)
        if isinstance(laid, Every):
            continue
        if placed.rest is None:
            del state.pending[index]
        else:
            state.pending[index] = placed.rest
            break

    _draw_kept_back(state, filled, at)
    return filled


def _reserved(state: _State, rows: range) -> int:
    """Rows kept back on every frame for the parts drawn at its foot."""
    total = 0
    for part in state.at_foot.values():
        rows_wanted = _height(part, rows)
        if rows_wanted == 0:
            #  It would decline a whole frame, so it would decline every frame,
            #  and reserving nothing for it would leave it silently undrawn.
            raise ValueError(f"{part!r} can never be placed: it is taller than a frame")
        total += rows_wanted
    return total


def _draw_kept_back(state: _State, filled: Filled, at: int) -> None:
    """Draw the parts whose rows were kept back, under what they follow.

    Kept back from the foot so that a flowing part cannot take them, but drawn
    where the content ended rather than at the foot itself. On a full frame the
    two are the same row; on a short one, a note that explains a table of four
    figures belongs under the table and not thirteen rows beneath it.
    """
    for part in state.at_foot.values():
        placed = part.place(filled.canvas, Room(at, ROWS - at, CHOICES_PER_FRAME))
        filled.offer = filled.offer.and_then(placed.offer)
        at += placed.rows


class Edge(Enum):
    """Which end of a frame a furnishing is docked to."""

    TOP = auto()
    FOOT = auto()


@dataclass(frozen=True)
class Summary:
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

    @property
    def page_number(self) -> str:
        """The page number as this frame displays it, or empty for none."""
        return self.address.frame_number(self.index) if self.address else ""


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

    def draw(self, canvas: Canvas, at: int, page: Summary) -> None:
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

    def draw(self, canvas: Canvas, at: int, page: Summary) -> None:
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

    def draw(self, canvas: Canvas, at: int, page: Summary) -> None:
        del page  # a rule says nothing about the page it is on
        rule(canvas, at, self.colour)


@dataclass(frozen=True)
class Prompt:
    """Every key that works on this frame, and what each of them does."""

    colour: Colour = Colour.YELLOW
    edge: Edge = Edge.FOOT
    rows: int = 1

    def draw(self, canvas: Canvas, at: int, page: Summary) -> None:
        said = render_footer(page.offered, ROOM)
        if said:
            canvas.row(at).text(fitted(said, COLUMNS - 1), self.colour)


#: What a page is furnished with unless a service or a page says otherwise: a
#: title above a rule, and a rule above the keys. Two levels of override, and
#: no cascade -- a site is one thing and a page that does something
#: irreversible may say so, but a reader learns where the page number sits once.
DEFAULT_FURNITURE: Final[tuple[Furnishing, ...]] = (
    Header(),
    Rule(edge=Edge.TOP),
    Rule(edge=Edge.FOOT),
    Prompt(),
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
    below = sum(one.rows for one in furniture if one.edge is Edge.FOOT)
    return range(above, ROWS - below)


@dataclass(kw_only=True)
class PageLayout:
    """A page as its furniture and the parts laid out between it.

    Construct one and call `build` with the address the page answers to.

    Attributes:
        title: What the header calls the page.
        parts: The content, in the order it appears down the frames.
        home: Where `0` leads from every frame, or None for no way home. A
            `Shortcut` where the footer should call it something other than
            "index", or where another key should do it.
        shortcuts: Keys offered on every frame, besides the digits and `0`.
        item: What `A` and `D` move between, as the footer says it.
        furniture: The bands round the content. Empty for a page that wants
            none, such as a masthead.
        follows: Where `#` leads once the frames have run out. Setting it
            answers the next-frame keys, the session trying the next frame
            before falling through to this.
        hang_up: Whether the line drops once the page has been shown.

    Example:
        A menu, with a lead-in on its first frame::

            PageLayout(
                title="LATEST POSTS",
                home=app.index,
                parts=[Once(preamble), Flowing(Menu(entries=posts))],
            ).build(address)
    """

    title: str = ""
    parts: Sequence[Laid] = ()
    home: "PageAddress | Shortcut | None" = None
    shortcuts: Sequence[Shortcut] = ()
    item: str = "item"
    furniture: Sequence[Furnishing] = DEFAULT_FURNITURE
    follows: PageAddress | None = None
    hang_up: bool = False

    @property
    def way_home(self) -> Shortcut | None:
        """The way home as a shortcut, whichever way the page gave it."""
        if self.home is None or isinstance(self.home, Shortcut):
            return self.home
        return Shortcut(key=HOME_KEY, destination=self.home, says="index")

    def build(self, address: PageAddress | None) -> Page:
        """Fill the frames with the parts, then furnish them.

        Args:
            address: The address this page answers to, from which each frame
                takes the page number it displays. None where the page has no
                number of its own.

        Returns:
            The finished page: one frame for each the parts needed, each
            carrying the keys that work while it is showing.
        """
        filled = fill(self.parts, content_rows(self.furniture))
        return Page(
            frames=tuple(
                self._frame(one, index, len(filled), address)
                for index, one in enumerate(filled)
            ),
            follows=self.follows,
            hang_up=self.hang_up,
        )

    def _frame(
        self, filled: Filled, index: int, frames: int, address: PageAddress | None
    ) -> PageFrame:
        """One frame, furnished, with the keys it answers gathered onto it."""
        back, on = index > 0, index + 1 < frames or self.follows is not None
        page = Summary(
            title=self.title,
            address=address,
            index=index,
            frames=frames,
            offered=self._offered(filled, back=back, on=on),
        )
        self._furnish(filled.canvas, page)
        return PageFrame(
            frame=filled.canvas.frame,
            choices=self._choices(filled),
            moves=moving(back=back, on=on),
            form=filled.offer.form,
        )

    def _furnish(self, canvas: Canvas, page: Summary) -> None:
        """Draw the bands, downwards from the top and upwards from the foot."""
        at = 0
        for one in self.furniture:
            if one.edge is Edge.TOP:
                one.draw(canvas, at, page)
                at += one.rows
        at = ROWS - sum(one.rows for one in self.furniture if one.edge is Edge.FOOT)
        for one in self.furniture:
            if one.edge is Edge.FOOT:
                one.draw(canvas, at, page)
                at += one.rows

    def _choices(self, filled: Filled) -> dict[str, PageAddress]:
        """Every key on this frame that leads somewhere else."""
        choices = dict(filled.offer.choices)
        choices |= {one.key: one.destination for one in self.shortcuts}
        choices |= arrows_lead_where(
            {one.key: one.destination for one in self.shortcuts if one.arrow}
        )
        if (way := self.way_home) is not None:
            choices[way.key] = way.destination
        return choices

    def _offered(self, filled: Filled, *, back: bool, on: bool) -> list[FooterItem]:
        """What the prompt should try to name, most worth saying last off."""
        items = list(filled.offer.named)
        #  A shortcut on one of the movement letters is named by `movement`
        #  rather than by itself, so that a page built here and a page drawn by
        #  hand describe the same key the same way.
        moves = {one.key for one in self.shortcuts if one.key in _MOVEMENT_LETTERS}
        items += [
            FooterItem(one.key, one.says, one.priority)
            for one in self.shortcuts
            if one.key not in moves
        ]
        items += movement(
            moves | {key for key, yes in ((PREVIOUS_FRAME, back), (NEXT_FRAME, on)) if yes},
            item=self.item,
        )
        if (way := self.way_home) is not None:
            items.append(
                FooterItem(
                    way.key, way.says, Priority.ESSENTIAL, brief=way.says.split(",")[0]
                )
            )
        return items

