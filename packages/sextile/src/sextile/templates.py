"""Pages made of rows, dealt into frames.

Five places had grown their own version of the same six steps -- take a list,
deal it into frames, draw the chrome, write the rows, wire up the keys, return a
`Page` -- and they had drifted, as five copies do. Two of them disagreed about
how much room a preamble costs, and one advertised a `1-9 select` on a frame
with nothing to select.

There are two shapes, and they differ in three things:

    Menu       nine to a frame, each entry numbered, a line of detail beneath
    Listing    twenty to a frame, nothing numbered, detail in a second column
    Prose      running text, wrapped, in whatever rows it takes

so `Template` does the six steps and a subclass says how tall an entry is, how
to draw one, and whether it can be chosen. An application wanting a fourth shape
subclasses it rather than starting again -- which is what the base class being
generic in *what* it deals is for: menus and listings deal entries, prose deals
rendered rows.

What a template consumes is the `Entry` protocol -- text, detail, and where it
leads -- so a service with its own richer notion of a menu entry passes that
instead of converting to somebody else's type. `MenuItem` is here for services
that have no such notion.
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, runtime_checkable

from sextile.addressing import PageAddress
from sextile.content.blocks import Document, Paragraph
from sextile.keys import CONVENTIONAL_NEXT_FRAME, NEXT_FRAME, PREVIOUS_FRAME
from sextile.page import Page, PageFrame
from sextile.viewdata.canvas import Canvas, RowWriter
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import cell_count
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.layout import Row, rows_for

if TYPE_CHECKING:
    from sextile.application import Sextile

#: A reader selects with one keypress, so nine is the most a frame can offer.
CHOICES_PER_FRAME: Final = 9

#: The digit that goes home, on every frame of every template.
HOME_KEY: Final = "0"


@runtime_checkable
class Entry(Protocol):
    """One line of a page made of rows.

    A protocol rather than a type, so that a service with its own idea of what
    a menu entry is -- carrying a post, a timestamp, whatever it needs later --
    hands that over instead of copying it into somebody else's dataclass.
    """

    @property
    def text(self) -> str:
        """What the line says."""

    @property
    def detail(self) -> str:
        """A second line, or a second column, or nothing."""

    @property
    def destination(self) -> PageAddress | None:
        """Where choosing it leads, or None if it is only to be read."""


@dataclass(frozen=True)
class MenuItem:
    """One selectable line, for a service with nothing richer of its own."""

    text: str
    detail: str = ""
    destination: PageAddress | None = None

    @classmethod
    def for_page(cls, app: "Sextile", name: str) -> "MenuItem":
        """A line taken from what the page said about itself when registered.

        The words are at the registration, so a menu offering a page and a list
        naming it cannot drift apart -- they are the same words.
        """
        about = app.page_info(name)
        if about is None:
            raise ValueError(f"{name!r} is not a page that says what it is")
        return cls(
            text=about.title, detail=about.detail, destination=app.address_for(name)
        )


class Template[E](ABC):
    """Rows dealt into frames, with the chrome and keys that go with them.

    A subclass says how tall an entry is, how to draw one, and whether entries
    can be chosen. Everything else -- pagination, the header, the prompt, the
    keys that move between frames, and the way home -- happens here, the same
    way on every page that uses one.
    """

    #: Rows one entry occupies, which decides how many fit on a frame.
    rows_per_entry: ClassVar[int] = 1

    #: Whether entries take a digit, and so whether they can be chosen.
    numbered: ClassVar[bool] = False

    #: What the prompt says about choosing, where there is anything to choose.
    selecting_hint: ClassVar[str] = ""

    def __init__(
        self,
        *,
        title: str,
        entries: Sequence[E],
        home: PageAddress | None = None,
        preamble: Sequence[str] = (),
        empty: str = "",
    ) -> None:
        self.title = title
        self.entries = entries
        self.home = home
        self.preamble = tuple(preamble)
        #  Said instead of showing an empty frame: on a service that answers
        #  slowly, nothing at all is indistinguishable from a fault.
        self.empty = empty

    # -- what a subclass decides --------------------------------------------

    @abstractmethod
    def draw(self, row: RowWriter, entry: E, digit: str | None) -> None:
        """Draw one entry's first row. Later rows are `draw_detail`'s."""

    #  Empty on purpose, and not abstract: a shape one row tall has no second
    #  row to draw.
    def draw_detail(self, row: RowWriter, entry: E) -> None:  # noqa: B027
        """Draw an entry's second row, where the shape has one."""

    def destination(self, entry: E) -> PageAddress | None:
        """Where choosing this entry leads. Nowhere, unless a shape says so."""
        del entry
        return None

    def prompt(self, *, selecting: bool, back: bool, on: bool) -> str:
        """Name every key that does something here, and no key that does not."""
        parts = []
        if selecting and self.selecting_hint:
            parts.append(self.selecting_hint)
        axis = _axis(back=back, on=on)
        if axis:
            parts.append(axis)
        if self.home is not None:
            parts.append(f"{HOME_KEY} index")
        return ", ".join(parts)

    # -- what the template does ---------------------------------------------

    def build(self, address: PageAddress) -> Page:
        """Deal the entries into frames and draw them."""
        batches = self._deal()
        frames = []
        for index, batch in enumerate(batches):
            canvas = Canvas()
            back, on = index > 0, index + 1 < len(batches)
            draw_chrome(
                canvas,
                title=self.title,
                page_number=address.frame_number(index),
                prompt=self.prompt(selecting=self.numbered and bool(batch), back=back, on=on),
            )
            row = self._draw_preamble(canvas) if index == 0 else CONTENT_FIRST_ROW
            choices: dict[str, PageAddress] = {}
            if self.home is not None:
                choices[HOME_KEY] = self.home
            if not batch and self.empty:
                canvas.row(row).text(_fitted(self.empty, COLUMNS - 1), Colour.WHITE)
            for offset, entry in enumerate(batch):
                digit = str(offset + 1) if self.numbered else None
                where = self.destination(entry) if digit is not None else None
                if digit is not None and where is not None:
                    choices[digit] = where
                self.draw(canvas.row(row), entry, digit)
                if self.rows_per_entry > 1 and row + 1 < _last_content_row():
                    self.draw_detail(canvas.row(row + 1), entry)
                row += self.rows_per_entry
            frames.append(
                PageFrame(
                    frame=canvas.frame,
                    choices=choices,
                    moves=_moves(back=back, on=on),
                )
            )
        return Page(frames=tuple(frames))

    def _draw_preamble(self, canvas: Canvas) -> int:
        """Draw the lead-in, and say which row the entries start on."""
        row = CONTENT_FIRST_ROW
        for line in self.preamble:
            if line:
                canvas.row(row).text(_fitted(line, COLUMNS - 1), Colour.WHITE)
            row += 1
        #  A blank row between the lead-in and the entries, so the two read as
        #  two things.
        return row + 1 if self.preamble else row

    def _deal(self) -> list[Sequence[E]]:
        """Entries, frame by frame. The first frame is the short one."""
        first = self._capacity(len(self.preamble) + (1 if self.preamble else 0))
        rest = self._capacity(0)
        batches: list[Sequence[E]] = []
        start = 0
        while start < len(self.entries):
            room = first if not batches else rest
            batches.append(self.entries[start : start + room])
            start += room
        return batches or [()]

    def _capacity(self, spent: int) -> int:
        """How many entries fit once ``spent`` rows have gone on other things."""
        room = max((CONTENT_ROWS - spent) // self.rows_per_entry, 1)
        return min(room, CHOICES_PER_FRAME) if self.numbered else room


class Menu(Template[Entry]):
    """Nine choices to a frame, each with a line of detail beneath it.

    The shape most viewdata pages take: a reader selects with one keypress, so
    nine is the most a frame can offer and the rest go on the next.
    """

    rows_per_entry = 2
    numbered = True
    selecting_hint = "1-9 select"

    def destination(self, entry: Entry) -> PageAddress | None:
        return entry.destination

    def draw(self, row: RowWriter, entry: Entry, digit: str | None) -> None:
        if digit is not None:
            row.text(f"{digit} ", Colour.YELLOW)
        row.text(_fitted(entry.text, COLUMNS - 4), Colour.WHITE)

    def draw_detail(self, row: RowWriter, entry: Entry) -> None:
        if entry.detail:
            row.skip(2).text(_fitted(entry.detail, COLUMNS - 4), Colour.GREEN)


class Listing(Template[Entry]):
    """Two columns, twenty to a frame, nothing to select.

    For a page that is a reference rather than a menu -- what a service is made
    of, which words it answers to. The left column is set to the widest entry,
    so the page reads as a table.
    """

    rows_per_entry = 1
    numbered = False

    #: Never wider than half the row: a truncated left column would be a page
    #: number that fetches the wrong page.
    _WIDEST: Final = COLUMNS // 2

    #: A cell for the colour of each column.
    _ATTRIBUTES: Final = 2

    def __init__(self, **wanted: object) -> None:
        super().__init__(**wanted)  # type: ignore[arg-type]
        widest = max((cell_count(entry.text) for entry in self.entries), default=0)
        self.column = min(widest + 1, self._WIDEST)

    def draw(self, row: RowWriter, entry: Entry, digit: str | None) -> None:
        del digit  # a listing numbers nothing
        row.text(_fitted(entry.text, self.column), Colour.YELLOW)
        row.skip(max(self.column - cell_count(entry.text), 0))
        row.text(
            _fitted(entry.detail, COLUMNS - self.column - self._ATTRIBUTES), Colour.WHITE
        )


class Prose(Template[Row]):
    """Running text, wrapped and dealt into frames.

    The third shape, and the one every notice page was writing out by hand --
    string literals broken at forty columns with blank strings for the gaps
    between paragraphs, which has to be redone by hand whenever a word changes
    and cannot survive a change of column width at all.

    What it deals is rendered rows rather than entries, which is what the base
    class is generic for. The rendering itself is `viewdata.layout`'s, so a
    notice gets the same treatment as a forum post: quotations in cyan, listings
    in green, nesting indented, over-long words split rather than dropped.
    """

    rows_per_entry = 1
    numbered = False

    @classmethod
    def of(
        cls,
        *paragraphs: str,
        title: str,
        home: PageAddress | None = None,
        preamble: Sequence[str] = (),
        empty: str = "",
    ) -> "Prose":
        """A page of plain paragraphs, wrapped here rather than by the caller."""
        return cls(
            title=title,
            entries=rows_for(
                Document(blocks=tuple(Paragraph((text,)) for text in paragraphs if text))
            ),
            home=home,
            preamble=preamble,
            empty=empty,
        )

    def draw(self, row: RowWriter, entry: Row, digit: str | None) -> None:
        del digit  # prose numbers nothing
        if entry.text:
            #  No truncation here: `layout` has already wrapped to the room a
            #  row has, colour attribute and indent included. Cutting again
            #  would take a character off every line it had filled exactly.
            row.skip(entry.indent).text(entry.text, entry.colour)


def _last_content_row() -> int:
    return CONTENT_FIRST_ROW + CONTENT_ROWS


def _moves(*, back: bool, on: bool) -> frozenset[str]:
    keys = set()
    if back:
        keys.add(PREVIOUS_FRAME)
    if on:
        #  `#` comes along wherever `S` does, so the conventional viewdata key
        #  keeps working for a reader who never learns the rest.
        keys.update({NEXT_FRAME, CONVENTIONAL_NEXT_FRAME})
    return frozenset(keys)


def _axis(*, back: bool, on: bool) -> str:
    if back and on:
        return f"{PREVIOUS_FRAME}{NEXT_FRAME} frame"
    if on:
        return f"{NEXT_FRAME} frame"
    if back:
        return f"{PREVIOUS_FRAME} frame"
    return ""


def _fitted(text: str, cells: int) -> str:
    fitted = text
    while cell_count(fitted) > cells:
        fitted = fitted[:-1]
    return fitted
