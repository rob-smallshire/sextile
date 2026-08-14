"""Sequences formatted as parts of a page.

A formatter is a `layout.Part` that lays out a homogeneous sequence: it takes
as many entries as the room allows, says which of them can be chosen, and hands
back the rest for the next frame. It knows nothing of titles, rules or keys,
which are the layout's.

The shapes ready to use, differing in how many entries a frame holds and how
each one is drawn:

    Menu       numbered, a line of detail beneath each
    Lines      lines drawn as given, for a page that simply says something

A service needing a shape that is not here subclasses `Formatter` or
`RowFormatter` and says how tall an entry is and how to draw one.

Example:
    Twelve entries, nine on the first frame and three on the second::

        PageLayout(
            title="LATEST POSTS",
            home=app.index,
            parts=[Flowing(Menu(entries=posts))],
        ).build(address)
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import ClassVar, Protocol, runtime_checkable

from sextile.addressing import PageAddress
from sextile.layout import Offer, Placement, Room
from sextile.viewdata.canvas import Canvas, RowWriter
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import fitted
from sextile.viewdata.footer import FooterItem, Priority
from sextile.viewdata.frame import COLUMNS


@runtime_checkable
class Entry(Protocol):
    """What a formatter over `Entry` values requires of them.

    A protocol rather than a base class, so that a service with its own idea of
    an entry, carrying a post or a timestamp or whatever it will need later,
    can pass that value directly rather than copy it into a dataclass belonging
    to the framework.
    """

    @property
    def text(self) -> str:
        """The text drawn on the entry's first row."""

    @property
    def detail(self) -> str:
        """A second line, a second column, or empty for neither."""

    @property
    def destination(self) -> PageAddress | None:
        """The address choosing this entry leads to, or None if it is only read."""


@dataclass(frozen=True)
class MenuItem:
    """An `Entry` for a service that has nothing richer of its own.

    Attributes:
        text: The text drawn on the entry's first row.
        detail: A second line, a second column, or empty for neither.
        destination: The address choosing it leads to, or None if it is only
            read.
    """

    text: str = ""
    detail: str = ""
    destination: PageAddress | None = None


@dataclass(frozen=True, kw_only=True)
class Formatter[E](ABC):
    """Abstract base for the formatters: a sequence, laid out as a part.

    A subclass says how tall an entry is and how to draw one; this class works
    out how many fit in the room it is given, draws them, and hands back what
    is left.

    Class attributes, overridden by a subclass to describe its shape:
        rows_per_entry: Rows one entry occupies.
        separation: Blank rows between one entry and the next, and not after
            the last of them.
        numbered: Whether entries take a digit, and so whether the reader can
            choose them.
        selecting_hint: What the prompt says about choosing, on frames with
            something to choose.

    Attributes:
        entries: The values to draw, in the order they are to appear.
        empty: Said in place of the entries where there are none. A service
            that answers slowly cannot let a frame come up empty and
            unexplained, because a reader cannot tell that from a fault.
    """

    rows_per_entry: ClassVar[int] = 1
    separation: ClassVar[int] = 0
    numbered: ClassVar[bool] = False
    selecting_hint: ClassVar[FooterItem | None] = None

    entries: Sequence[E]
    empty: str = ""

    @abstractmethod
    def draw_entry(
        self, canvas: Canvas, row: int, entry: E, digit: str | None
    ) -> None:
        """Draw one entry in the `rows_per_entry` rows beginning at `row`.

        Args:
            canvas: The frame being drawn.
            row: The row the entry begins on.
            entry: The value to draw.
            digit: The key that chooses this entry, or None where this shape is
                not `numbered`.
        """

    def destination(self, entry: E) -> PageAddress | None:
        """The address choosing `entry` leads to, or None where it leads nowhere.

        Returns None for every entry unless a subclass overrides this.
        """
        del entry
        return None

    def place(self, canvas: Canvas, room: Room) -> Placement:
        """Draw as many entries as the room allows, and hand back the rest."""
        if not self.entries:
            return self._nothing(canvas, room)
        taking = self._fitting(room)
        if taking == 0:
            return Placement(rows=0, rest=self)
        choices: dict[str, PageAddress] = {}
        row = room.first_row
        for offset, entry in enumerate(self.entries[:taking]):
            digit = str(offset + 1) if self.numbered else None
            where = self.destination(entry) if digit is not None else None
            if digit is not None and where is not None:
                choices[digit] = where
            self.draw_entry(canvas, row, entry, digit)
            row += self.rows_per_entry + self.separation
        rest = self.entries[taking:]
        return Placement(
            rows=taking * (self.rows_per_entry + self.separation) - self.separation,
            offer=Offer(
                choices=choices,
                named=[self.selecting_hint] if choices and self.selecting_hint else [],
            ),
            rest=replace(self, entries=rest) if rest else None,
        )

    def _fitting(self, room: Room) -> int:
        """How many entries go in this room.

        The separation falls between entries and not after the last of them, so
        there is one separation more room than there appears to be: five
        three-row entries with a blank between them occupy nineteen rows rather
        than twenty.
        """
        fits = (room.rows + self.separation) // (self.rows_per_entry + self.separation)
        if self.numbered:
            fits = min(fits, room.choices)
        return max(min(fits, len(self.entries)), 0)

    def _nothing(self, canvas: Canvas, room: Room) -> Placement:
        """What to draw where there are no entries: a reason, or nothing."""
        if not self.empty:
            return Placement(rows=0)
        if room.rows < 1:
            return Placement(rows=0, rest=self)
        canvas.row(room.first_row).text(fitted(self.empty, COLUMNS - 1), Colour.WHITE)
        return Placement(rows=1)


@dataclass(frozen=True, kw_only=True)
class RowFormatter[E](Formatter[E]):
    """Abstract base for formatters whose entries are written along their rows.

    Implements `draw_entry` by calling `draw` for an entry's first row and
    `draw_detail` for its second, each with a `RowWriter` that runs from left
    to right. A shape positioned by cell, a picture several rows tall among
    them, should subclass `Formatter` and implement `draw_entry` itself.
    """

    @abstractmethod
    def draw(self, row: RowWriter, entry: E, digit: str | None) -> None:
        """Write an entry's first row."""

    #  Empty on purpose, and not abstract: an entry one row tall has no second
    #  row to write.
    def draw_detail(self, row: RowWriter, entry: E) -> None:  # noqa: B027
        """Write an entry's second row, where `rows_per_entry` allows one."""

    def draw_entry(
        self, canvas: Canvas, row: int, entry: E, digit: str | None
    ) -> None:
        self.draw(canvas.row(row), entry, digit)
        if self.rows_per_entry > 1:
            self.draw_detail(canvas.row(row + 1), entry)


@dataclass(frozen=True, kw_only=True)
class Menu(RowFormatter[Entry]):
    """Numbered choices, each with a line of detail beneath it.

    The shape most viewdata pages take. A reader chooses with a single
    keypress, so nine entries are the most one frame can offer and the rest go
    on the frames after it.
    """

    rows_per_entry: ClassVar[int] = 2
    numbered: ClassVar[bool] = True
    selecting_hint: ClassVar[FooterItem | None] = FooterItem(
        "1-9", "select", Priority.PRIMARY
    )

    def destination(self, entry: Entry) -> PageAddress | None:
        return entry.destination

    def draw(self, row: RowWriter, entry: Entry, digit: str | None) -> None:
        if digit is not None:
            row.text(f"{digit} ", Colour.YELLOW)
        row.text(fitted(entry.text, COLUMNS - 4), Colour.WHITE)

    def draw_detail(self, row: RowWriter, entry: Entry) -> None:
        if entry.detail:
            row.skip(2).text(fitted(entry.detail, COLUMNS - 4), Colour.GREEN)


@dataclass(frozen=True, kw_only=True)
class Lines(Formatter[str]):
    """Lines drawn as given, one to a row, for a page that says something.

    Not prose, which wraps running text and puts a blank row between one
    paragraph and the next. A notice that has arranged its own lines and its
    own blanks means them where they are, so nothing is wrapped and nothing is
    moved: a line too long for the row is cut.

    Attributes:
        said: The lines, in the order they are to appear. An empty one leaves a
            blank row.
    """

    entries: Sequence[str] = ()
    said: Sequence[str] = ()

    def __post_init__(self) -> None:
        #  `said` is what a caller writes, `entries` what a formatter divides.
        #  They are one sequence under two names, the second being the word
        #  that means something on a page of prose.
        if self.said and not self.entries:
            object.__setattr__(self, "entries", tuple(self.said))
        object.__setattr__(self, "said", tuple(self.entries))

    def draw_entry(
        self, canvas: Canvas, row: int, entry: str, digit: str | None
    ) -> None:
        del digit  # a notice numbers nothing
        if entry:
            canvas.row(row).text(fitted(entry, COLUMNS - 1), Colour.WHITE)
