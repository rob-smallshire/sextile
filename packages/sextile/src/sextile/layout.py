"""Parts laid out down the frames of a page.

A page's content is a short list of parts. Each is drawn once, drawn on every
frame, or broken across as many frames as it takes, and the order of the list
settles what sits above what. `fill` walks them and returns as many frames as
they needed. This is the first of the two passes that build a page: it does not
decide the frame count in advance and draws no furniture; the second pass does
both, once the count is known.

See [design.md](../../docs/design.md#laying-out-a-page) for the design this
implements and the reasoning behind it.

Example:
    A lead-in on the first frame, a heading on all of them, and a menu that
    goes on for as long as it goes on::

        fill(
            [OnOneFrame(preamble), OnEveryFrame(headings), Flow(Menu(items))],
            content_rows(DEFAULT_FURNITURE),
        )
"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING, Final, Protocol, runtime_checkable

from sextile.addressing import FRAMES_PER_PAGE, PageAddress, keyed
from sextile.keys import (
    ARROW_FOR,
    NEXT_FRAME,
    NEXT_ITEM,
    PREVIOUS_FRAME,
    PREVIOUS_ITEM,
    frame_moves,
    with_arrow_choices,
)
from sextile.page import Page, PageFrame
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import rule
from sextile.viewdata.encoding import cell_count, fitted
from sextile.viewdata.footer import FOOTER_WIDTH, FooterItem, Priority, movement, render_footer
from sextile.viewdata.frame import COLUMNS, ROWS
from sextile.viewdata.typesetting import TRUNCATION_NOTICE

if TYPE_CHECKING:
    from sextile.requests import Neighbours, PageRequest

__all__ = [
    "CHOICES_PER_FRAME",
    "DEFAULT_FURNITURE",
    "DEFAULT_HOME",
    "DefaultHome",
    "FrameBreak",
    "Drawable",
    "Custom",
    "Edge",
    "OnEveryFrame",
    "Flow",
    "Furnishing",
    "HOME_KEY",
    "Header",
    "OnOneFrame",
    "PageLayout",
    "Part",
    "Placed",
    "Claim",
    "Footer",
    "Space",
    "Rule",
    "Shortcut",
    "FrameContext",
    "content_rows",
]

if TYPE_CHECKING:
    from sextile.forms import Form


@dataclass(frozen=True)
class Space:
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
class Claim:
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

    def merged_with(self, other: "Claim") -> "Claim":
        """This claim and another, as one.

        Args:
            other: What a later part on the same frame claimed.

        Returns:
            The two merged. Where both claim the same key the later wins,
            which cannot arise between the digits of two flowing parts because
            the second is given only the choices the first left.

        Raises:
            ValueError: If both carry a form. A frame has one field to type
                into; `forms.FieldSet` is what composes several into one.
        """
        if self.form is not None and other.form is not None:
            raise ValueError("a frame can carry only one form")
        return Claim(
            choices={**self.choices, **other.choices},
            named=[*self.named, *other.named],
            form=self.form or other.form,
        )


@dataclass(frozen=True)
class Placed:
    """What placing a drawable on one frame came to.

    Attributes:
        rows: The rows it used, which is nought where it would not begin here.
        claim: What it claims on this frame.
        remainder: What is left of it for the next frame, or None where it is
            finished. A drawable that returns nought rows and itself is asking
            for a frame of its own.
    """

    rows: int
    claim: Claim = Claim()
    remainder: "Drawable | None" = None


@runtime_checkable
class Drawable(Protocol):
    """Something drawn between the rules: a menu, some lines, a picture, a form.

    A drawable is a description rather than a position, so placing one does not
    change it and a layout may be built more than once. The exception is a
    form, which holds what has been typed.
    """

    def place(self, canvas: Canvas, room: Space) -> Placed:
        """Draw as much as `room` allows, and say what is left over.

        Args:
            canvas: The frame being filled.
            room: What the frame has left to give.

        Returns:
            The rows used, what they claim, and whatever remains for the next
            frame. Returning nought rows and `self` asks for a fresh frame,
            which is how a drawable too tall for what is left is carried whole
            to the next frame rather than split.
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
        label: How the footer names the key. Put the short form first: the
            footer sheds words from the end when a row is tight, so
            `"index, or key another page"` degrades to `"index"` and then to
            the bare key.
        with_arrow: Whether the matching cursor key leads there as well. Only `W`,
            `A`, `S` and `D` have one; asking on any other key adds nothing
            rather than raising.
        priority: How hard the footer tries to keep it. A key that is the
            point of the page outranks one that is a convenience.

    A page's digits belong to its entries and change from frame to frame, but a
    shortcut is fixed. It is for the way out that is not the way home, such as a
    page returning to the one that led to it.
    """

    key: str
    destination: PageAddress
    label: str = ""
    #  Not assumed, because whether an arrow means what its letter means
    #  depends on what is on the frame: on a page with a coordinate field it
    #  does not, `W` being West and `S` South.
    with_arrow: bool = False
    priority: Priority = Priority.PRIMARY


@dataclass(frozen=True)
class Custom:
    """A part of a stated height, drawn cell by cell by the page itself.

    A picture is positioned at a cell and may be several rows tall, which suits
    a strip of mosaics or a grid of figures and does not suit a line of text.

    Attributes:
        rows: How many rows of the frame it occupies.
        draw: Called with the canvas and the row it begins on.

    Example:
        A month as a grid of weeks, which is the whole of a page's content::

            OnOneFrame(Custom(rows=1 + len(weeks), draw=lambda canvas, row: ...))
    """

    rows: int
    draw: "Callable[[Canvas, int], None]"

    def place(self, canvas: Canvas, room: Space) -> Placed:
        if room.rows < self.rows:
            return Placed(rows=0, remainder=self)
        self.draw(canvas, room.first_row)
        return Placed(rows=self.rows)


@dataclass(frozen=True)
class OnOneFrame:
    """A drawable drawn one time, at its place in the order.

    On the first frame where nothing flowing comes before it, and otherwise on
    whichever frame the flow before it finished on.
    """

    drawable: Drawable


@dataclass(frozen=True)
class OnEveryFrame:
    """A drawable drawn on every frame, at its place in the order.

    Where it comes after any flowing part, its rows are kept back at the foot
    of every frame before the flowing part is placed, since a flowing part
    takes the rows left to it and nothing after one would be drawn at all.
    Where it comes before them all, it is drawn where it stands. Several of
    either follow one another in the order the list gives them.
    """

    drawable: Drawable


@dataclass(frozen=True)
class Flow:
    """A drawable broken across as many frames as it takes.

    Several may appear in one list, and they follow one another: the second
    begins in the row after the first has finished, on whatever frame that is.
    """

    drawable: Drawable


@dataclass(frozen=True)
class FrameBreak:
    """A division the page means, rather than one the rows forced.

    Whatever follows begins on a new frame. A break that would divide nothing
    is ignored: one at either end of the list, two together, or one on a frame
    with nothing yet drawn on it.
    """


#: One of a page's parts: a `Drawable` with the frames it appears on
#: (`OnOneFrame`, `OnEveryFrame` or `Flow`), a `FrameBreak`, or a bare `Drawable`, which means
#: `Flow` -- flowing across as many frames as it takes is what a part does
#: unless it says otherwise, and it is the only sensible reading of one given
#: without a wrapper.
type Part = OnOneFrame | OnEveryFrame | Flow | FrameBreak | Drawable

#: A part once a bare drawable has been read as `Flow`: what the filling
#: works in, every part carrying its own `drawable`.
_Placed = OnOneFrame | OnEveryFrame | Flow | FrameBreak


def _placed(part: Part) -> _Placed:
    """Read a bare drawable in a parts list as a flowing part."""
    if isinstance(part, OnOneFrame | OnEveryFrame | Flow | FrameBreak):
        return part
    return Flow(part)


@dataclass
class _FilledFrame:
    """One frame's content, before any furniture is drawn on it.

    Attributes:
        canvas: The frame, with the content drawn and the furniture rows left
            alone.
        claim: Everything the parts on this frame claimed, merged.
    """

    canvas: Canvas
    claim: Claim = field(default_factory=Claim)


#: The four letters that move about, which are the ones an arrow stands for.
_MOVEMENT_LETTERS: Final = frozenset(ARROW_FOR)

#: The digits a frame can offer, a reader choosing with one keypress. Held here
#: rather than in a sequence part because it is a fact about the keypad and the
#: whole frame shares it, however many parts divide it up.
CHOICES_PER_FRAME = 9


def fill(parts: Sequence[Part], rows: range) -> list[_FilledFrame]:
    """Draw the parts onto as many frames as they take.

    Args:
        parts: The page's content, in the order it is to appear.
        rows: The rows of a frame the content may use, the furniture having
            taken the rest.

    Returns:
        One `_FilledFrame` a frame, in order, and never none: a page that answered
        with no frames could not be shown. Stops at `FRAMES_PER_PAGE`, a page
        having frames `a` to `z` and no more, and says so on the last row of
        the last of them rather than ending without explanation.

    Raises:
        ValueError: If a part can never be placed, being taller than a whole
            frame, or if two parts on one frame both carry a form.
    """
    state = _State([_placed(part) for part in parts])
    frames: list[_FilledFrame] = []
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
    list: a `OnOneFrame` that has been drawn and a `Flow` that has run out are
    both absent from it.
    """

    parts: Sequence[_Placed]
    pending: dict[int, Drawable] = field(default_factory=dict)
    broken: set[int] = field(default_factory=set)
    at_foot: dict[int, Drawable] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.pending = {
            index: part.drawable
            for index, part in enumerate(self.parts)
            if not isinstance(part, FrameBreak)
        }
        self.at_foot = _at_foot(self.parts)

    @property
    def finished(self) -> bool:
        """Whether anything is left that is not drawn on every frame."""
        return not any(
            index in self.pending
            for index, part in enumerate(self.parts)
            if not isinstance(part, OnEveryFrame | FrameBreak)
        )


def _at_foot(parts: Sequence[_Placed]) -> dict[int, Drawable]:
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
        (index for index, part in enumerate(parts) if isinstance(part, Flow)),
        len(parts),
    )
    return {
        index: part.drawable
        for index, part in enumerate(parts)
        if index > flowing and isinstance(part, OnEveryFrame)
    }


def _height(drawable: Drawable, rows: range) -> int:
    """How many rows a drawable takes on a whole frame.

    Measured by placing it on a canvas that is then thrown away. A drawable is
    a description and placing one does not change it, so the second placing --
    the one that counts -- draws the same thing in the row it belongs on.
    """
    return drawable.place(
        Canvas(), Space(rows.start, len(rows), CHOICES_PER_FRAME)
    ).rows


def _frame(state: _State, rows: range) -> _FilledFrame:
    """Fill one frame, taking as much of what is pending as will go on it."""
    filled = _FilledFrame(canvas=Canvas())
    #  A part at the end of the list that is drawn on every frame is charged
    #  its rows before anything flowing is asked for its, or the flow takes
    #  them and the note beneath it is written over.
    reserved = _reserved(state, rows)
    at, left = rows.start, len(rows) - reserved
    choices = CHOICES_PER_FRAME
    drawn = False

    for index, part in enumerate(state.parts):
        if isinstance(part, FrameBreak):
            #  A break on a frame with nothing on it yet would make an empty
            #  one, and a break already honoured is not a second division.
            if drawn and index not in state.broken:
                state.broken.add(index)
                break
            continue
        if index in state.at_foot:
            continue
        drawable = state.pending.get(index)
        if drawable is None:
            continue
        placed = drawable.place(filled.canvas, Space(at, left, choices))
        if placed.rows == 0 and placed.remainder is drawable:
            if not drawn:
                raise ValueError(f"{drawable!r} can never be placed: it is taller than a frame")
            break
        drawn = True
        filled.claim = filled.claim.merged_with(placed.claim)
        at, left = at + placed.rows, left - placed.rows
        choices -= len(placed.claim.choices)
        if isinstance(part, OnEveryFrame):
            continue
        if placed.remainder is None:
            del state.pending[index]
        else:
            state.pending[index] = placed.remainder
            break

    _draw_kept_back(state, filled, at)
    return filled


def _reserved(state: _State, rows: range) -> int:
    """Rows kept back on every frame for the parts drawn at its foot."""
    total = 0
    for drawable in state.at_foot.values():
        rows_wanted = _height(drawable, rows)
        if rows_wanted == 0:
            #  It would decline a whole frame, so it would decline every frame,
            #  and reserving nothing for it would leave it silently undrawn.
            raise ValueError(f"{drawable!r} can never be placed: it is taller than a frame")
        total += rows_wanted
    return total


def _draw_kept_back(state: _State, filled: _FilledFrame, at: int) -> None:
    """Draw the parts whose rows were kept back, under what they follow.

    Kept back from the foot so that a flowing part cannot take them, but drawn
    where the content ended rather than at the foot itself. On a full frame the
    two are the same row; on a short one, a note that explains a table of four
    figures belongs under the table and not thirteen rows beneath it.
    """
    for drawable in state.at_foot.values():
        placed = drawable.place(filled.canvas, Space(at, ROWS - at, CHOICES_PER_FRAME))
        filled.claim = filled.claim.merged_with(placed.claim)
        at += placed.rows


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


class DefaultHome:
    """Sentinel for a `home` left unset, so the app's index stands in for it."""


#: `home` was not given, so `build` takes the way home from `request.app.index`.
#: Distinct from `None`, which is a page saying it offers no way home at all.
DEFAULT_HOME: Final = DefaultHome()


def _way_home(home: "PageAddress | Shortcut | None") -> Shortcut | None:
    """The way home as a shortcut, whichever way the page gave it."""
    if home is None or isinstance(home, Shortcut):
        return home
    return Shortcut(key=HOME_KEY, destination=home, label="index")


@dataclass(kw_only=True)
class PageLayout:
    """A page as its furniture and the parts laid out between it.

    Construct one and call `build` with the request the page answers.

    Attributes:
        title: What the header calls the page. `None` takes the registered
            title of `request.address`, upper-cased; `""` heads it with nothing.
        parts: The content, in the order it appears down the frames. A bare
            `Drawable` means `Flow(drawable)`; `OnOneFrame`, `OnEveryFrame` and `FrameBreak`
            say the frames a part appears on where they are not the default.
        home: Where `0` leads from every frame. Unset takes `request.app.index`;
            `None` offers no way home; a `PageAddress` leads there under the
            `index` label; a `Shortcut` where the footer should call it
            something else, or another key should do it.
        numbered: Whether the header shows the page number. `False` for a page
            with a header but no number a reader could key, such as a notice.
        shortcuts: Keys offered on every frame, besides the digits and `0`.
        neighbours: The pages either side of this one in the sequence being
            read. Given, it wires `A` to `previous` and `D` to `next` (with
            their cursor-key arrows) wherever each is not None, and the footer
            names them. Pass `request.neighbours`; a page reached by keying its
            number carries a `Neighbours` of two Nones and offers neither.
        item_noun: What `A` and `D` move between, as the footer says it.
        furniture: The bands round the content. Empty for a page that wants
            none, such as a masthead.
        next_page: Where `#` leads once the frames have run out. Setting it
            answers the next-frame keys, the session trying the next frame
            before falling through to this.
        hang_up: Whether the line drops once the page has been shown.

    Example:
        A menu, with a lead-in on its first frame::

            PageLayout(
                title="LATEST POSTS",
                parts=[OnOneFrame(preamble), Flow(Menu(entries=posts))],
            ).build(request)
    """

    title: str | None = None
    parts: Sequence[Part] = ()
    home: "PageAddress | Shortcut | None | DefaultHome" = DEFAULT_HOME
    numbered: bool = True
    shortcuts: Sequence[Shortcut] = ()
    neighbours: "Neighbours | None" = None
    item_noun: str = "item"
    furniture: Sequence[Furnishing] = DEFAULT_FURNITURE
    next_page: PageAddress | None = None
    hang_up: bool = False

    def _shortcuts(self) -> tuple[Shortcut, ...]:
        """The page's own shortcuts, and the `A`/`D` keys `neighbours` wires.

        A neighbour is a shortcut on a movement letter, so `_offered` names it
        through `movement` rather than by itself -- which is how a page built
        here and a page drawn by hand describe the same key the same way.
        """
        wired = []
        if self.neighbours is not None:
            if self.neighbours.previous is not None:
                wired.append(Shortcut(PREVIOUS_ITEM, self.neighbours.previous, with_arrow=True))
            if self.neighbours.next is not None:
                wired.append(Shortcut(NEXT_ITEM, self.neighbours.next, with_arrow=True))
        return (*self.shortcuts, *wired)

    def build(self, request: "PageRequest") -> Page:
        """Fill the frames with the parts, then furnish them.

        The title, the way home and the page number are taken from the request
        where the page did not give them: the registered title of
        `request.address`, `request.app.index`, and `request.address` itself.

        Args:
            request: The request this page answers, supplying the address it is
                at and the service it belongs to.

        Returns:
            The finished page: one frame for each the parts needed, each
            carrying the keys that work while it is showing.
        """
        #  A page that gave no title of its own is headed with the registered
        #  title of its address, shouted, or with its keyed number where the
        #  address is unrouted or untitled. A title the page did give is drawn
        #  as it is, so a forum name or a place name keeps its own case.
        if self.title is not None:
            title = self.title
        else:
            registered = request.app.title_for(request.address)
            title = (registered or keyed(request.address)).upper()
        home = request.app.index if isinstance(self.home, DefaultHome) else self.home
        return self._render(address=request.address, title=title, home=home)

    def _render(
        self, *, address: PageAddress | None, title: str, home: "PageAddress | Shortcut | None"
    ) -> Page:
        """Build the frames from resolved values, the request already read."""
        filled = fill(self.parts, content_rows(self.furniture))
        return Page(
            frames=tuple(
                self._frame(one, index, len(filled), address, title=title, home=home)
                for index, one in enumerate(filled)
            ),
            next_page=self.next_page,
            hang_up=self.hang_up,
        )


    def _frame(
        self,
        filled: _FilledFrame,
        index: int,
        frames: int,
        address: PageAddress | None,
        *,
        title: str,
        home: "PageAddress | Shortcut | None",
    ) -> PageFrame:
        """One frame, furnished, with the keys it answers gathered onto it."""
        back, on = index > 0, index + 1 < frames or self.next_page is not None
        page = FrameContext(
            title=title,
            address=address,
            index=index,
            frames=frames,
            numbered=self.numbered,
            offered=self._offered(filled, back=back, on=on, home=home),
        )
        self._furnish(filled.canvas, page)
        return PageFrame(
            frame=filled.canvas.frame,
            choices=self._choices(filled, home=home),
            moves=frame_moves(has_previous=back, has_next=on),
            form=filled.claim.form,
        )

    def _furnish(self, canvas: Canvas, page: FrameContext) -> None:
        """Draw the bands, downwards from the top and upwards from the foot."""
        at = 0
        for one in self.furniture:
            if one.edge is Edge.TOP:
                one.draw(canvas, at, page)
                at += one.rows
        at = ROWS - sum(one.rows for one in self.furniture if one.edge is Edge.BOTTOM)
        for one in self.furniture:
            if one.edge is Edge.BOTTOM:
                one.draw(canvas, at, page)
                at += one.rows

    def _choices(
        self, filled: _FilledFrame, *, home: "PageAddress | Shortcut | None"
    ) -> dict[str, PageAddress]:
        """Every key on this frame that leads somewhere else."""
        shortcuts = self._shortcuts()
        choices = dict(filled.claim.choices)
        choices |= {one.key: one.destination for one in shortcuts}
        choices |= with_arrow_choices(
            {one.key: one.destination for one in shortcuts if one.with_arrow}
        )
        if (way := _way_home(home)) is not None:
            choices[way.key] = way.destination
        return choices

    def _offered(
        self, filled: _FilledFrame, *, back: bool, on: bool, home: "PageAddress | Shortcut | None"
    ) -> list[FooterItem]:
        """What the prompt should try to name, most worth saying last off."""
        shortcuts = self._shortcuts()
        items = list(filled.claim.named)
        #  A shortcut on one of the movement letters is named by `movement`
        #  rather than by itself, so that a page built here and a page drawn by
        #  hand describe the same key the same way.
        moves = {one.key for one in shortcuts if one.key in _MOVEMENT_LETTERS}
        items += [
            FooterItem(one.key, one.label, one.priority)
            for one in shortcuts
            if one.key not in moves
        ]
        items += movement(
            moves | {key for key, yes in ((PREVIOUS_FRAME, back), (NEXT_FRAME, on)) if yes},
            item=self.item_noun,
        )
        if (way := _way_home(home)) is not None:
            items.append(
                FooterItem(
                    way.key, way.label, Priority.ESSENTIAL, brief=way.label.split(",")[0]
                )
            )
        return items

