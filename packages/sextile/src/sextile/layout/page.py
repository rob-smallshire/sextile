"""A page as its furniture and the parts laid out between it.

`PageLayout` is what a service constructs and calls `build` on. It fills the
frames with the parts (the first pass, in `parts`), then furnishes each frame
now that the count is known (the second pass, in `furniture`), and gathers onto
each frame the keys that work while it is showing: the parts' own choices, the
shortcuts a page offers on every frame, the keys that move between frames, and
the way home.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from sextile.keys import (
    ARROW_FOR,
    NEXT_FRAME,
    NEXT_ITEM,
    PREVIOUS_FRAME,
    PREVIOUS_ITEM,
    frame_moves,
    with_arrow_choices,
)
from sextile.layout.footer import FooterItem, Priority, movement
from sextile.layout.furniture import (
    DEFAULT_FURNITURE,
    Edge,
    FrameContext,
    Furnishing,
    content_rows,
)
from sextile.layout.parts import Part, _FilledFrame, fill
from sextile.page import Page, PageAddress, PageFrame, keyed
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.frame import ROWS

if TYPE_CHECKING:
    from sextile.requests import Neighbours, PageRequest

#: The key that leads home, on every frame of every page that offers one.
HOME_KEY: Final = "0"

#: The four letters that move about, which are the ones an arrow stands for.
_MOVEMENT_LETTERS: Final = frozenset(ARROW_FOR)


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
