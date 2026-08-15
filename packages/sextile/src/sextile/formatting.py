"""Sequences formatted as parts of a page.

A sequence part is a `layout.Drawable` that lays out a homogeneous sequence: it takes
as many entries as the room allows, says which of them can be chosen, and hands
back the rest for the next frame. It deals only with the entries; titles, rules
and keys are the layout's.

The shapes ready to use, differing in how many entries a frame holds and how
each one is drawn:

    Menu       numbered, a line of detail beneath each
    Listing    two columns, nothing numbered, for a page that is a reference
    Figures    a label and a figure a row, the figures aligned in one column
    Lines      lines drawn as given, for a page that simply says something
    Prose      running text, wrapped, in as many rows as it takes

A service needing a shape that is not here subclasses `SequencePart` or
`RowSequencePart` and says how tall an entry is and how to draw one.

Example:
    Twelve entries, nine on the first frame and three on the second::

        PageLayout(
            title="LATEST POSTS",
            parts=[Menu(entries=posts)],
        ).build(request)
"""

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import ClassVar, Protocol, runtime_checkable

from sextile.content.blocks import Document, Paragraph
from sextile.layout import Claim, Placed, Space
from sextile.layout.footer import FooterItem, Priority
from sextile.page import PageAddress
from sextile.viewdata.canvas import Canvas, RowWriter
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import key_row
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.measure import cell_count, fitted
from sextile.viewdata.typesetting import Row, rows_for
from sextile.viewdata.wrapping import wrap_within

__all__ = [
    "Entry",
    "Figures",
    "SequencePart",
    "Lines",
    "Listing",
    "Menu",
    "MenuItem",
    "NumberedRowSequencePart",
    "Prose",
    "RowSequencePart",
]



@runtime_checkable
class Entry(Protocol):
    """What a sequence part over `Entry` values requires of them.

    A protocol rather than a base class, so that a service with its own richer
    entry type, carrying whatever it needs, can pass that value directly rather
    than copy it into a dataclass belonging to the framework.
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
class SequencePart[E](ABC):
    """Abstract base for the sequence parts: a sequence, laid out as a part.

    A subclass says how tall an entry is and how to draw one; this class works
    out how many fit in the room it is given, draws them, and hands back what
    is left.

    Class attributes, overridden by a subclass to describe its shape:
        rows_per_entry: Rows one entry occupies.
        gap: Blank rows between one entry and the next, and not after
            the last of them.
        numbered: Whether entries take a digit, and so whether the reader can
            choose them.
        choose_hint: What the prompt says about choosing, on frames with
            something to choose.

    Attributes:
        entries: The values to draw, in the order they are to appear.
        empty: Said in place of the entries where there are none. A service
            that answers slowly cannot let a frame come up empty and
            unexplained, because a reader cannot tell that from a fault.
    """

    rows_per_entry: ClassVar[int] = 1
    gap: ClassVar[int] = 0
    numbered: ClassVar[bool] = False
    choose_hint: ClassVar[FooterItem | None] = None

    entries: Sequence[E]
    empty: str = ""

    @abstractmethod
    def draw_entry(self, canvas: Canvas, row: int, entry: E) -> None:
        """Draw one entry in the `rows_per_entry` rows beginning at `row`.

        Args:
            canvas: The frame being drawn.
            row: The row the entry begins on.
            entry: The value to draw.

        A numbered part is drawn its digit for it: `NumberedRowSequencePart`
        draws the digit column before the entry, so a subclass never sees the
        digit and every part but a numbered one is spared the parameter.
        """

    def _draw_entry(self, canvas: Canvas, row: int, entry: E, digit: str | None) -> None:
        """Draw one entry, given the digit that chooses it where there is one.

        The one place the loop hands a part its digit. The base drops it; a
        numbered part overrides this to draw the digit column with it.
        """
        del digit
        self.draw_entry(canvas, row, entry)

    def destination(self, entry: E) -> PageAddress | None:
        """The address choosing `entry` leads to, or None where it leads nowhere.

        Returns None for every entry unless a subclass overrides this.
        """
        del entry
        return None

    def place(self, canvas: Canvas, space: Space) -> Placed:
        """Draw as many entries as the room allows, and hand back the rest."""
        if not self.entries:
            return self._nothing(canvas, space)
        taking = self._fitting(space)
        if taking == 0:
            return Placed(rows=0, remainder=self)
        choices: dict[str, PageAddress] = {}
        row = space.first_row
        for offset, entry in enumerate(self.entries[:taking]):
            digit = str(offset + 1) if self.numbered else None
            where = self.destination(entry) if digit is not None else None
            if digit is not None and where is not None:
                choices[digit] = where
            self._draw_entry(canvas, row, entry, digit)
            row += self.rows_per_entry + self.gap
        rest = self.entries[taking:]
        return Placed(
            rows=taking * (self.rows_per_entry + self.gap) - self.gap,
            claim=Claim(
                choices=choices,
                named=[self.choose_hint] if choices and self.choose_hint else [],
            ),
            remainder=replace(self, entries=rest) if rest else None,
        )

    def _fitting(self, space: Space) -> int:
        """How many entries go in this space.

        The gap falls between entries and not after the last of them, so
        there is one gap more room than there appears to be: five
        three-row entries with a blank between them occupy nineteen rows rather
        than twenty.
        """
        fits = (space.rows + self.gap) // (self.rows_per_entry + self.gap)
        if self.numbered:
            fits = min(fits, space.choices)
        return max(min(fits, len(self.entries)), 0)

    def _nothing(self, canvas: Canvas, space: Space) -> Placed:
        """What to draw where there are no entries: a reason, or nothing."""
        if not self.empty:
            return Placed(rows=0)
        if space.rows < 1:
            return Placed(rows=0, remainder=self)
        canvas.row(space.first_row).text(fitted(self.empty, COLUMNS - 1), Colour.WHITE)
        return Placed(rows=1)


@dataclass(frozen=True, kw_only=True)
class RowSequencePart[E](SequencePart[E]):
    """Abstract base for sequence parts whose entries are written along their rows.

    Implements `draw_entry` by calling `draw` for an entry's first row and
    `draw_detail` for its second, each with a `RowWriter` that runs from left
    to right. A shape positioned by cell, a picture several rows tall among
    them, should subclass `SequencePart` and implement `draw_entry` itself.
    """

    @abstractmethod
    def draw(self, row: RowWriter, entry: E) -> None:
        """Write an entry's first row."""

    #  Empty on purpose, and not abstract: an entry one row tall has no second
    #  row to write.
    def draw_detail(self, row: RowWriter, entry: E) -> None:  # noqa: B027
        """Write an entry's second row, where `rows_per_entry` allows one."""

    def draw_entry(self, canvas: Canvas, row: int, entry: E) -> None:
        self.draw(canvas.row(row), entry)
        if self.rows_per_entry > 1:
            self.draw_detail(canvas.row(row + 1), entry)


@dataclass(frozen=True, kw_only=True)
class NumberedRowSequencePart[E](RowSequencePart[E]):
    """A row sequence part whose entries a reader chooses by a digit.

    Only a numbered part takes a digit, so only this one has it in its drawing
    path: it draws the digit column -- a yellow `1 ` before the entry -- and
    `draw` writes the entry after it, in the room the digit has left. `Menu` is
    the one shape built on it; a service numbering its own entries subclasses
    this rather than reaching for the digit itself.
    """

    numbered: ClassVar[bool] = True

    def _draw_entry(self, canvas: Canvas, row: int, entry: E, digit: str | None) -> None:
        writer = canvas.row(row)
        if digit is not None:
            writer.text(f"{digit} ", Colour.YELLOW)
        self.draw(writer, entry)
        if self.rows_per_entry > 1:
            self.draw_detail(canvas.row(row + 1), entry)


@dataclass(frozen=True, kw_only=True)
class Menu(NumberedRowSequencePart[Entry]):
    """Numbered choices, each with a line of detail beneath it.

    The shape most viewdata pages take. A reader chooses with a single
    keypress, so nine entries are the most one frame can offer and the rest go
    on the frames after it.
    """

    rows_per_entry: ClassVar[int] = 2
    choose_hint: ClassVar[FooterItem | None] = FooterItem(
        "1-9", "select", Priority.PRIMARY
    )

    def destination(self, entry: Entry) -> PageAddress | None:
        return entry.destination

    def draw(self, row: RowWriter, entry: Entry) -> None:
        #  The digit column is already drawn; the entry follows in the room it
        #  left, which is why the width is the row less the four cells the digit
        #  and the two colour attributes spend.
        row.text(fitted(entry.text, COLUMNS - 4), Colour.WHITE)

    def draw_detail(self, row: RowWriter, entry: Entry) -> None:
        if entry.detail:
            row.skip(2).text(fitted(entry.detail, COLUMNS - 4), Colour.GREEN)


@dataclass(frozen=True, kw_only=True)
class Lines(SequencePart[str]):
    """Lines drawn as given, one to a row, for a page that says something.

    Not prose, which wraps running text and puts a blank row between one
    paragraph and the next. A notice that has arranged its own lines and its
    own blanks means them where they are, so nothing is wrapped and nothing is
    moved: a line too long for the row is cut.

    Attributes:
        entries: The lines, in the order they are to appear, passed first and
            without a keyword. An empty one leaves a blank row.
        colour: What they are drawn in. White for a notice; green for a note
            beneath a table, set apart from the table above it.
    """

    entries: Sequence[str] = field(default=(), kw_only=False)
    colour: Colour = Colour.WHITE

    def draw_entry(
        self, canvas: Canvas, row: int, entry: str
    ) -> None:
        if entry:
            canvas.row(row).text(fitted(entry, COLUMNS - 1), self.colour)


@dataclass(frozen=True, kw_only=True)
class Listing(RowSequencePart[Entry]):
    """Two columns, nothing to choose, for a page that is a reference.

    What a service is made of, which words it answers to. The left column is
    set to the width of the widest entry, so that the page reads as a table,
    and a detail too long for the room left over is carried on to a further row
    rather than being cut.

    Attributes:
        column: How wide the left column is. Worked out from the entries when
            the listing is first made, and carried from frame to frame
            thereafter -- a table that set its column afresh on each frame
            would shift its columns partway down.
    """

    #  Never wider than half the row: a truncated left column here would be a
    #  page number that fetches the wrong page.
    _WIDEST: ClassVar[int] = COLUMNS // 2

    #: One cell for the colour attribute of each column.
    ATTRIBUTES: ClassVar[int] = 2

    column: int | None = None

    @classmethod
    def widest(cls) -> int:
        """The greatest width the left column can take, in cells.

        For a caller sizing the right-hand column, which gets whatever is left
        over. Computed here so a page need not repeat the arithmetic.
        """
        return cls._WIDEST

    def __post_init__(self) -> None:
        #  `column` set means this listing came from another by `replace`, so
        #  its entries are wrapped already and its column is the one the frames
        #  before it used. Only a listing made by a caller prepares itself.
        if self.column is not None:
            return
        widest = max((cell_count(entry.text) for entry in self.entries), default=0)
        object.__setattr__(self, "column", min(widest + 1, self._WIDEST))
        object.__setattr__(self, "entries", self._carried(self.entries))

    def _carried(self, entries: Sequence[Entry]) -> list[Entry]:
        """The entries, with any detail too long for its column carried on.

        The right-hand column gets whatever the left leaves, which is enough
        for a short detail and not for a long one. Cut, such a detail reads as a
        fault rather than as a shortage of room; carried on to a row with an
        empty left column, it reads as what it is, because which column a thing
        is in is what tells the two apart.

        Two rows at most: a detail needing a third wants rewriting, a listing
        being a table rather than a place for prose.
        """
        assert self.column is not None
        cells = COLUMNS - self.column - self.ATTRIBUTES
        carried: list[Entry] = []
        for entry in entries:
            lines = wrap_within(entry.detail, cells=cells, rows=2) or [""]
            carried.append(entry)
            carried += [MenuItem(text="", detail=line) for line in lines[1:]]
            if len(lines) > 1:
                carried[-2] = MenuItem(
                    text=entry.text, detail=lines[0], destination=entry.destination
                )
        return carried

    def draw(self, row: RowWriter, entry: Entry) -> None:
        assert self.column is not None
        key_row(row, entry.text, entry.detail, column=self.column)


@dataclass(frozen=True, kw_only=True)
class Figures(RowSequencePart[Entry]):
    """A label and a figure a row, the figures right-aligned in one column.

    For a page that reports rather than offers: how many callers, how much is
    held, how long since. The entry's `text` is the label and its `detail` the
    figure, written out as the page wants it read.

    Attributes:
        label_width: How wide the labels' column is, in cells, and
            `figure_width` how wide the figures'. Worked out once and carried,
            as a `Listing`'s column is.
        figure_width: See `label_width`.
    """

    #: Two cells of margin before the label. A table of figures reads as a
    #: block rather than as a list, and a block wants a margin.
    INDENT: ClassVar[int] = 2

    #: A cell between the longest label and its figure, over and above the
    #: attribute cell that colours the figure.
    _GAP: ClassVar[int] = 1

    #: One cell for the colour attribute of each column.
    ATTRIBUTES: ClassVar[int] = 2

    label_width: int | None = None
    figure_width: int | None = None

    def __post_init__(self) -> None:
        if self.label_width is not None:
            return
        figure = max((cell_count(one.detail) for one in self.entries), default=0)
        widest = max((cell_count(one.text) for one in self.entries), default=0)
        cells = COLUMNS - self.INDENT - figure - self.ATTRIBUTES
        object.__setattr__(self, "figure_width", figure)
        object.__setattr__(self, "label_width", min(widest + self._GAP, cells))

    def draw(self, row: RowWriter, entry: Entry) -> None:
        assert self.label_width is not None and self.figure_width is not None
        row.skip(self.INDENT)
        #  The label is padded rather than the figure indented, so that one
        #  long label pushes the whole column of figures right and no figure
        #  ends up under a label.
        row.text(fitted(entry.text, self.label_width).ljust(self.label_width), Colour.WHITE)
        row.text(entry.detail.rjust(self.figure_width), Colour.CYAN)


@dataclass(frozen=True, kw_only=True)
class Prose(SequencePart[Row]):
    """Running text, wrapped, in as many rows as it takes.

    Its entries are rendered `Row` values rather than `Entry` values. Laying
    the text out through `viewdata.typesetting` gives a notice the same
    treatment as any long document: quotations in cyan, listings in green,
    nesting indented, and over-long words broken rather than dropped.
    """

    @classmethod
    def of(cls, *paragraphs: str) -> "Prose":
        """Build prose from plain paragraphs, wrapping them on the way.

        Args:
            *paragraphs: The text, one string a paragraph, in the order it is
                to be read. Empty strings are dropped; the gaps between
                paragraphs come from the layout.

        Returns:
            The prose, ready to be laid out as a part.
        """
        return cls(
            entries=rows_for(
                Document(blocks=tuple(Paragraph((text,)) for text in paragraphs if text))
            )
        )

    def draw_entry(
        self, canvas: Canvas, row: int, entry: Row
    ) -> None:
        if entry.text:
            #  No truncation here: `typesetting` has already wrapped to the room
            #  a row has, colour attribute and indent included. Cutting again
            #  would take a character off every line it had filled exactly.
            canvas.row(row).skip(entry.indent).text(entry.text, entry.colour)


