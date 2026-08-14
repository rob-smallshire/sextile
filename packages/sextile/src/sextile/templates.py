"""Divide a sequence of entries into the frames of a page, and draw them.

The shapes ready to use, differing in how many entries a frame holds and how
each one is drawn:

    Menu       nine entries a frame, each numbered, a line of detail beneath
    Listing    twenty entries a frame, none numbered, detail in a second column
    Figures    a label and a figure a row, the figures aligned in one column
    Lines      lines drawn as given, for a page that simply says something
    Prose      running text, wrapped, in as many rows as it takes

`Template` performs the part they have in common: dividing the entries between
frames, drawing the chrome, composing the prompt, and wiring up the keys that
move from one frame to the next. A subclass supplies `rows_per_entry`, a
`draw_entry`, and whether entries are `numbered`.

A service needing a shape that is not here subclasses `Template` or
`RowTemplate` rather than starting again, which is why the base class is
generic in the type of its entries: most of them divide up `Entry` values,
`Prose` divides up rendered `Row` values.

A template will accept anything satisfying the `Entry` protocol, so a service
with a richer notion of a menu entry can pass that rather than convert it to a
type of the framework's choosing. `MenuItem` is here for services with no such
notion of their own.
"""

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, runtime_checkable

from sextile.addressing import FRAMES_PER_PAGE, PageAddress
from sextile.content.blocks import Document, Paragraph
from sextile.keys import (
    ARROW_FOR,
    NEXT_FRAME,
    PREVIOUS_FRAME,
    arrows_lead_where,
    moving,
)
from sextile.page import Page, PageFrame
from sextile.viewdata.canvas import Canvas, RowWriter, Run
from sextile.viewdata.chrome import CONTENT_FIRST_ROW, CONTENT_ROWS, draw_chrome
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import key_row
from sextile.viewdata.encoding import cell_count, fitted
from sextile.viewdata.footer import ROOM, FooterItem, Priority, movement, render_footer
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.typesetting import TRUNCATION_NOTICE, Row, rows_for
from sextile.viewdata.wrapping import wrap_text, wrap_within

if TYPE_CHECKING:
    from sextile.application import Sextile

@dataclass(frozen=True)
class Shortcut:
    """A key offered on every frame of a page, always leading to one address.

    Attributes:
        key: The character the reader presses, such as `*` or `R`.
        destination: The address that key leads to, from every frame.
        says: How the footer names the key. Put the short form first: the
            footer sheds words from the end when a row is tight, so
            `"index, or key another page"` degrades to `"index"` and then to
            the bare key. Empty leaves it at the bare key throughout.
        arrow: Whether the matching cursor key leads there as well. Only `W`,
            `A`, `S` and `D` have one; asking on any other key adds nothing
            rather than raising, so a page listing its shortcuts need not know
            which of them happen to be movement letters.

    A page's digits belong to its entries and change from frame to frame, but a
    shortcut is fixed. It is for the way out that is not the way home: a
    forecast returning to the search that found it, a post returning to the
    board it was on. `0` is the equivalent key for the index, and a shortcut is
    that idea generalised, so that the framework need not know what else a
    service might want one for.
    """

    key: str
    destination: PageAddress
    says: str = ""
    #  Not assumed, because whether an arrow means what its letter means
    #  depends on what is on the frame: on a page with a coordinate field it
    #  does not, `W` being West and `S` South, and a reader reaching for the
    #  up arrow would silently type a letter into a coordinate.
    arrow: bool = False


@dataclass(frozen=True)
class Block:
    """A part of a preamble that is drawn cell by cell rather than written.

    Attributes:
        rows: How many rows of the frame the block occupies.
        draw: Called with the canvas and the row the block begins on.

    A picture is positioned by cell and may be several rows tall, which suits a
    strip of mosaics and does not suit a line of text. `Template` counts a
    block's rows along with all the others, so a preamble that fills the first
    frame leaves no entries on it instead of overrunning the rule at its foot.
    """

    rows: int
    draw: "Callable[[Canvas, int], None]"


#: One line of a preamble: plain text in white, a sequence of coloured runs
#: where the colours carry part of the meaning, or a `Block` of rows the page
#: draws itself. `Template` counts the rows of all three the same way.
type PreambleLine = str | Sequence[Run] | Block

#: The most entries one frame can offer a choice of, a reader choosing with a
#: single keypress.
CHOICES_PER_FRAME: Final = 9

#: The key that leads home, on every frame of every template.
HOME_KEY: Final = "0"

#: One cell for the colour attribute of each of two columns, which a template
#: setting one column against another has to leave room for.
_ATTRIBUTES: Final = 2


@runtime_checkable
class Entry(Protocol):
    """What `Menu` and `Listing` require of the values they are given.

    A protocol rather than a base class, so that a service with its own idea of
    a menu entry, carrying a post or a timestamp or whatever it will need
    later, can pass that value directly rather than copy it into a dataclass
    belonging to the framework.
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

    text: str
    detail: str = ""
    destination: PageAddress | None = None

    @classmethod
    def for_page(cls, app: "Sextile", name: str) -> "MenuItem":
        """Build an item from what a page recorded about itself at registration.

        Args:
            app: The application the page is registered with.
            name: The name the page was registered under.

        Returns:
            An item carrying the page's title and detail, leading to its
            address.

        Raises:
            ValueError: If no page is registered under `name`.

        The words come from the registration, so a menu offering a page and a
        listing naming it cannot drift apart: they are the same words.
        """
        about = app.page_info(name)
        if about is None:
            raise ValueError(f"{name!r} is not a page that says what it is")
        return cls(
            text=about.title, detail=about.detail, destination=app.address_for(name)
        )


@dataclass(kw_only=True, eq=False)
class Template[E](ABC):
    """Abstract base for the templates: builds a `Page` from a list of entries.

    Construct a concrete template with the entries and the surrounding text,
    then call `build` with the address the page answers to. A subclass decides
    how an entry is drawn and how much room it takes; this class divides the
    entries between frames, draws the chrome, composes the prompt, and wires up
    the keys.

    Subclasses must implement `draw_entry` and will usually override
    `rows_per_entry`, `numbered` and `destination`. Templates whose entries are
    written along their rows should subclass `RowTemplate` instead, which
    implements `draw_entry` in terms of a simpler `draw`.

    Class attributes, overridden by a subclass to describe its shape:
        rows_per_entry: Rows one entry occupies, which fixes how many entries
            fit on a frame.
        separation: Blank rows between one entry and the next, and not after
            the last of them.
        numbered: Whether entries take a digit, and so whether the reader can
            choose them.
        selecting_hint: What the prompt says about choosing, on frames with
            something to choose.

    Attributes:
        title: The heading drawn at the top of every frame.
        entries: The values to draw, in the order they are to appear.
        home: Where `0` leads from every frame, or None to offer no way home.
            A `Shortcut` instead of an address where the page wants the footer
            to call it something other than "index", or to put it on another
            key.
        preamble: Lines drawn above the entries on the first frame only.
        empty: Text drawn in place of the entries when there are none.
        headings: A row labelling the columns, drawn on every frame.
        shortcuts: Keys offered on every frame, besides the digits and `0`.
        item: What `A` and `D` move between, as the footer says it: "previous
            day", "next post". Only the noun; the framework has the rest.
        footnote: Said beneath the entries on every frame, wrapped to the room
            a row has.

    Type parameters:
        E: What one entry is. `Menu` and `Listing` fix this as `Entry`; a
            subclass may fix it as whatever it draws, as `Prose` does with
            `Row`.

    Example:
        A shape of its own, four rows to an entry and nothing selectable::

            @dataclass(kw_only=True, eq=False)
            class ForecastTable(Template[Day]):
                rows_per_entry = 4
                separation = 1
                numbered = False

                today: date

                def draw_entry(self, canvas, row, entry, digit):
                    draw_day(canvas, row, entry, self.today)

            page = ForecastTable(
                title="TRONDHEIM", entries=days, home=INDEX, today=today
            ).build(address)
    """

    rows_per_entry: ClassVar[int] = 1

    #  The separation goes between entries rather than beneath each of them: an
    #  entry several rows tall needs air around it or two of them read as one
    #  block, but charging that air to every entry would waste a row at the foot
    #  of the frame, where the chrome's rule already does the same job.
    separation: ClassVar[int] = 0

    numbered: ClassVar[bool] = False

    selecting_hint: ClassVar[FooterItem | None] = None

    title: str

    entries: Sequence[E]

    home: "PageAddress | Shortcut | None" = None

    preamble: Sequence[PreambleLine] = ()

    #  A service that answers slowly cannot let a frame come up empty and
    #  unexplained, because the reader cannot tell that from a fault.
    empty: str = ""

    #  Headings are drawn on every frame, where a preamble is drawn on the
    #  first: a reader on frame c looking at a column of figures has no way
    #  back to the words that say what they are.
    headings: str = ""

    #  Named in the prompt, so that a page cannot offer a key silently.
    shortcuts: Sequence[Shortcut] = ()

    #  What `A` and `D` move between, for the footer to say: a day, a post, a
    #  place. The words round it are the framework's, so a page built here and
    #  a page drawn by hand describe the same key the same way; what the page
    #  supplies is the noun. Not what `W` and `S` move between, which is always
    #  the frames of the one thing.
    item: str = "item"

    #  Beneath the entries on every frame, for the same reason the headings sit
    #  above them on every frame: a reader on frame c looking at a column of
    #  figures has no way back to the words that say what they are.
    footnote: str = ""

    def __post_init__(self) -> None:
        self.shortcuts = tuple(self.shortcuts)
        self.preamble = tuple(self.preamble)

    # -- what a subclass decides --------------------------------------------

    @abstractmethod
    def draw_entry(
        self, canvas: Canvas, row: int, entry: E, digit: str | None
    ) -> None:
        """Draw one entry in the `rows_per_entry` rows beginning at `row`.

        Args:
            canvas: The frame being drawn, which the entry writes into.
            row: The row the entry begins on, counting from the top of the
                frame.
            entry: The value to draw.
            digit: The key that chooses this entry, or None where the template
                is not `numbered`.

        This takes a canvas and a row number rather than a `RowWriter` because
        a mosaic picture is positioned by cell and may be several rows tall. A
        row writer runs along a single row from left to right, which suits
        everything except a picture, and `RowTemplate` provides it.
        """

    @property
    def way_home(self) -> "Shortcut | None":
        """The way home as a shortcut, whichever way the page gave it.

        Returns:
            `0` leading to the address given, called "index", where `home` is
            an address; the shortcut itself where the page supplied one; None
            where the page offers no way home at all.
        """
        if self.home is None or isinstance(self.home, Shortcut):
            return self.home
        return Shortcut(key=HOME_KEY, destination=self.home, says="index")

    def destination(self, entry: E) -> PageAddress | None:
        """The address choosing `entry` leads to, or None where it leads nowhere.

        Returns None for every entry unless a subclass overrides this.
        """
        del entry
        return None

    def prompt(self, *, selecting: bool, back: bool, on: bool) -> str:
        """Compose the footer, naming every key that works on this frame.

        Args:
            selecting: Whether the digits `1-9` choose an entry here.
            back: Whether a previous frame exists to go back to.
            on: Whether a further frame exists to go on to.

        Returns:
            The footer text, fitted to the room a frame has for it.

        The keys are assembled as `FooterItem` values rather than as a string,
        so that a frame with room can spell out what each key does and only a
        crowded one falls back to bare letters.
        """
        items = []
        if selecting and self.selecting_hint is not None:
            items.append(self.selecting_hint)
        #  A shortcut on one of the movement letters is named by `movement`
        #  rather than by itself. Naming it twice is how two pages of one
        #  service come to describe the same key differently, which is what
        #  `movement` was extracted to stop; `ARROW_FOR` is the four letters,
        #  those being exactly the ones an arrow stands for.
        moves = {
            shortcut.key for shortcut in self.shortcuts if shortcut.key in ARROW_FOR
        }
        items += [
            FooterItem(shortcut.key, shortcut.says, Priority.PRIMARY)
            for shortcut in self.shortcuts
            if shortcut.key not in moves
        ]
        items += movement(
            moves
            | {
                key
                for key, answered in ((PREVIOUS_FRAME, back), (NEXT_FRAME, on))
                if answered
            },
            item=self.item,
        )
        if (way := self.way_home) is not None:
            items.append(
                FooterItem(
                    way.key,
                    way.says,
                    Priority.ESSENTIAL,
                    brief=way.says.split(",")[0],
                )
            )
        return render_footer(items, ROOM)

    # -- what the template does ---------------------------------------------

    def build(self, address: PageAddress | None) -> Page:
        """Divide the entries between frames and draw each frame.

        Args:
            address: The address this page answers to, from which each frame
                takes the page number it displays. None where the page has no
                number of its own -- a notice given in reply to a number that
                answers nothing -- and the title then has the header to itself.

        Returns:
            The finished page: one `PageFrame` for each frame, in order, each
            carrying the keys that work while it is showing. A page with no
            entries at all is one empty frame rather than none.
        """
        batches, truncated = self._deal()
        frames = []
        for index, batch in enumerate(batches):
            canvas = Canvas()
            back, on = index > 0, index + 1 < len(batches)
            draw_chrome(
                canvas,
                title=self.title,
                page_number=address.frame_number(index) if address else "",
                prompt=self.prompt(selecting=self.numbered and bool(batch), back=back, on=on),
            )
            row = self._draw_preamble(canvas) if index == 0 else CONTENT_FIRST_ROW
            #  Headings label a column of figures, so a frame with no figures
            #  on it has nothing for them to label.
            if self.headings and batch:
                canvas.row(row).text(fitted(self.headings, COLUMNS - 1), Colour.CYAN)
                row += 1
            choices: dict[str, PageAddress] = {
                shortcut.key: shortcut.destination for shortcut in self.shortcuts
            } | arrows_lead_where(
                {
                    shortcut.key: shortcut.destination
                    for shortcut in self.shortcuts
                    if shortcut.arrow
                }
            )
            if (way := self.way_home) is not None:
                choices[way.key] = way.destination
            if not batch and self.empty:
                canvas.row(row).text(fitted(self.empty, COLUMNS - 1), Colour.WHITE)
                row += 1
            for offset, entry in enumerate(batch):
                digit = str(offset + 1) if self.numbered else None
                where = self.destination(entry) if digit is not None else None
                if digit is not None and where is not None:
                    choices[digit] = where
                self.draw_entry(canvas, row, entry, digit)
                row += self.rows_per_entry + self.separation
            if truncated and index + 1 == len(batches):
                canvas.row(row).text(TRUNCATION_NOTICE, Colour.RED)
                row += 1
            self._draw_footnote(canvas, row)
            frames.append(
                PageFrame(
                    frame=canvas.frame,
                    choices=choices,
                    moves=moving(back=back, on=on),
                )
            )
        return Page(frames=tuple(frames))

    def _draw_preamble(self, canvas: Canvas) -> int:
        """Draw the preamble, returning the row the entries begin on."""
        row = CONTENT_FIRST_ROW
        for line in self.preamble:
            if isinstance(line, Block):
                line.draw(canvas, row)
            elif isinstance(line, str):
                if line:
                    canvas.row(row).text(fitted(line, COLUMNS - 1), Colour.WHITE)
            else:
                canvas.row(row).runs(line)
            row += _rows_of(line)
        #  A blank row between the preamble and the entries, so that the two
        #  read as two things.
        return row + 1 if self.preamble else row

    def _draw_footnote(self, canvas: Canvas, row: int) -> None:
        """Say what the entries mean, a blank row below the last of them."""
        if not self.footnote:
            return
        for offset, line in enumerate(self._footnote_lines(), start=1):
            canvas.row(row + offset).text(line, Colour.GREEN)

    def _footnote_lines(self) -> Sequence[str]:
        return wrap_text(self.footnote, COLUMNS - 1) if self.footnote else ()

    @property
    def footnote_rows(self) -> int:
        """Rows the footnote occupies, including the blank row above it."""
        lines = self._footnote_lines()
        return len(lines) + 1 if lines else 0

    @property
    def preamble_rows(self) -> int:
        """Rows the preamble occupies, including the blank row after it."""
        if not self.preamble:
            return 0
        return sum(_rows_of(line) for line in self.preamble) + 1

    def _deal(self) -> tuple[list[Sequence[E]], bool]:
        """The entries, grouped a frame at a time.

        Returns:
            The groups, and whether entries were left over. The first group is
            the smaller, the preamble having taken rows from it, and it is
            empty where the preamble took the whole frame. There is always at
            least one group, empty if there are no entries.
        """
        #  Headings cost their row on every frame, not only the first: counting
        #  them once would write the last entry of every later frame over the
        #  rule at the foot of it.
        #  A footnote is charged the same way and for the same reason.
        fixed = (1 if self.headings else 0) + self.footnote_rows
        first = self._capacity(self.preamble_rows + fixed)
        rest = max(self._capacity(fixed), 1)
        batches: list[Sequence[E]] = []
        start = 0
        while start < len(self.entries):
            room = first if not batches else rest
            if room == 0:
                #  A preamble that fills the frame. The entries begin on the
                #  next one rather than being squeezed on to this.
                batches.append(())
                continue
            batches.append(self.entries[start : start + room])
            start += room
        #  A page has frames a to z and no more, so a list long enough to
        #  exhaust them stops rather than building a frame that cannot be
        #  numbered. One entry comes off the last frame to leave room to say so.
        if len(batches) > FRAMES_PER_PAGE:
            batches = batches[:FRAMES_PER_PAGE]
            batches[-1] = batches[-1][:-1]
            return batches, True
        return batches or [()], False

    def _capacity(self, spent: int) -> int:
        """How many entries fit in a frame once `spent` rows have gone elsewhere.

        Args:
            spent: Rows already given to the preamble and the headings.

        Returns:
            The number of entries that will fit, never more than
            `CHOICES_PER_FRAME` where the template is `numbered`. Nought is a
            real answer, meaning the preamble has taken the whole frame.

        The separation falls between entries and not after the last of them, so
        there is one separation more room than there appears to be: five
        three-row entries with a blank between them occupy nineteen rows rather
        than twenty.
        """
        left = CONTENT_ROWS - spent + self.separation
        room = max(left // (self.rows_per_entry + self.separation), 0)
        return min(room, CHOICES_PER_FRAME) if self.numbered else room


class RowTemplate[E](Template[E]):
    """Abstract base for templates whose entries are written along their rows.

    Implements `draw_entry` by calling `draw` for an entry's first row and
    `draw_detail` for its second, each with a `RowWriter` that runs from left
    to right. This is what most pages want. A template positioning its entries
    by cell, a picture several rows tall among them, should subclass `Template`
    and implement `draw_entry` itself rather than leave `draw` empty.
    """

    @abstractmethod
    def draw(self, row: RowWriter, entry: E, digit: str | None) -> None:
        """Write an entry's first row.

        Args:
            row: A writer positioned at the start of the entry's first row.
            entry: The value to write.
            digit: The key that chooses this entry, or None where the template
                is not `numbered`.
        """

    #  Empty on purpose, and not abstract: an entry one row tall has no second
    #  row to write.
    def draw_detail(self, row: RowWriter, entry: E) -> None:  # noqa: B027
        """Write an entry's second row, where `rows_per_entry` allows one.

        Args:
            row: A writer positioned at the start of the entry's second row.
            entry: The value to write.

        Does nothing unless a subclass overrides it.
        """

    def draw_entry(
        self, canvas: Canvas, row: int, entry: E, digit: str | None
    ) -> None:
        self.draw(canvas.row(row), entry, digit)
        if self.rows_per_entry > 1 and row + 1 < _last_content_row():
            self.draw_detail(canvas.row(row + 1), entry)


class Menu(RowTemplate[Entry]):
    """Up to nine numbered choices a frame, each with a line of detail beneath.

    The shape most viewdata pages take. A reader chooses with a single
    keypress, so nine entries are the most one frame can offer and the rest go
    on the frames after it.

    Example::

        Menu(title="INDEX", entries=items, home=INDEX).build(address)
    """

    rows_per_entry = 2
    numbered = True
    selecting_hint = FooterItem("1-9", "select", Priority.PRIMARY)

    def destination(self, entry: Entry) -> PageAddress | None:
        return entry.destination

    def draw(self, row: RowWriter, entry: Entry, digit: str | None) -> None:
        if digit is not None:
            row.text(f"{digit} ", Colour.YELLOW)
        row.text(fitted(entry.text, COLUMNS - 4), Colour.WHITE)

    def draw_detail(self, row: RowWriter, entry: Entry) -> None:
        if entry.detail:
            row.skip(2).text(fitted(entry.detail, COLUMNS - 4), Colour.GREEN)


class Listing(RowTemplate[Entry]):
    """Two columns, twenty entries a frame, none of them selectable.

    For a page that is a reference rather than a menu: what a service is made
    of, which words it answers to. The left column is set to the width of the
    widest entry, so that the page reads as a table.

    A detail too long for the room left over is carried on to a further row
    with an empty left column, rather than being cut.

    Example::

        Listing(title="PAGES", entries=items, home=INDEX).build(address)
    """

    rows_per_entry = 1
    numbered = False

    #  Never wider than half the row: a truncated left column here would be a
    #  page number that fetches the wrong page.
    _WIDEST: Final = COLUMNS // 2

    #: One cell for the colour attribute of each column.
    ATTRIBUTES: Final = 2

    @classmethod
    def widest(cls) -> int:
        """The greatest width the left column can take, in cells.

        Returns:
            The width, whatever the entries; the column may come out narrower.

        For a caller sizing the right-hand column, which has whatever is left
        over. Without this, a page wrapping a long title into that column would
        work the same arithmetic out again and get it slightly different.
        """
        return cls._WIDEST

    def __post_init__(self) -> None:
        super().__post_init__()
        widest = max((cell_count(entry.text) for entry in self.entries), default=0)
        self.column = min(widest + 1, self._WIDEST)
        self.entries = self._wrapped(self.entries)

    def _wrapped(self, entries: Sequence[Entry]) -> list[Entry]:
        """The entries, with any detail too long for its column carried on.

        Args:
            entries: The entries as the caller gave them.

        Returns:
            The entries in order, each followed by a further entry holding the
            rest of its detail where the detail did not fit on one row. A
            carried row has empty text, so nothing appears in the left column
            and the destination stays with the first row. Two rows at most: a
            detail needing a third wants rewriting, a listing being a table
            rather than a place for prose.

        The right-hand column gets whatever the left leaves, which is enough
        for `One day` and not for `Forecast by lat/lon position`. Cut, such a
        detail reads as a fault rather than as a shortage of room; carried on
        to a row with an empty left column, it reads as what it is, because
        which column a thing is in is what tells the two apart.
        """
        room = COLUMNS - self.column - _ATTRIBUTES
        carried: list[Entry] = []
        for entry in entries:
            lines = wrap_within(entry.detail, cells=room, rows=2) or [""]
            carried.append(entry)
            carried += [MenuItem(text="", detail=line) for line in lines[1:]]
            if len(lines) > 1:
                carried[-2] = MenuItem(
                    text=entry.text, detail=lines[0], destination=entry.destination
                )
        return carried

    def draw(self, row: RowWriter, entry: Entry, digit: str | None) -> None:
        del digit  # a listing numbers nothing
        key_row(row, entry.text, entry.detail, column=self.column)


class Figures(RowTemplate[Entry]):
    """A label and a figure a row, the figures right-aligned in one column.

    For a page that reports rather than offers: how many callers, how much is
    held, how long since. The entry's `text` is the label and its `detail` is
    the figure, already written out as the page wants it read. Nothing is
    selectable, a figure being something to look at rather than somewhere to
    go.

    The figures share a column and are right-aligned within it, so that their
    units line up under each other. A column of numbers that does not line up
    is a column a reader has to check twice.

    Example::

        Figures(
            title="WHO HAS CALLED",
            entries=[MenuItem(text=said, detail=str(count)) for said, count in counts],
            home=INDEX,
            empty="Nobody has called yet.",
            footnote="A caller is one connection.",
        ).build(address)
    """

    rows_per_entry = 1
    numbered = False

    #: Two cells of margin before the label. A table of figures reads as a
    #: block rather than as a list, and a block wants a margin.
    INDENT: Final = 2

    #: A cell between the longest label and its figure, over and above the
    #: attribute cell that colours the figure. Without it the widest label in
    #: the table runs straight into the number beside it.
    _GAP: Final = 1

    def __post_init__(self) -> None:
        super().__post_init__()
        self.figure = max(
            (cell_count(entry.detail) for entry in self.entries), default=0
        )
        widest = max((cell_count(entry.text) for entry in self.entries), default=0)
        self.label = min(widest + self._GAP, self._room())

    def _room(self) -> int:
        """The most the labels may take, the figures having their column first."""
        return COLUMNS - self.INDENT - self.figure - _ATTRIBUTES

    def draw(self, row: RowWriter, entry: Entry, digit: str | None) -> None:
        del digit  # a figure numbers nothing
        row.skip(self.INDENT)
        #  The label is padded rather than the figure indented, so that one
        #  long label pushes the whole column of figures right and no figure
        #  ends up under a label.
        row.text(fitted(entry.text, self.label).ljust(self.label), Colour.WHITE)
        row.text(entry.detail.rjust(self.figure), Colour.CYAN)


class Lines(RowTemplate[str]):
    """Lines drawn as given, one to a row, for a page that says something.

    Not `Prose`, which wraps running text and puts a blank row between one
    paragraph and the next. A notice that has arranged its own lines and its
    own blanks means them where they are, so nothing is wrapped and nothing is
    moved: a line too long for the row is cut. There are more lines than a
    frame holds only when a page has said a great deal, and they go on to the
    next frame like any other entries.

    Example::

        Lines(
            title="UNKNOWN PAGE",
            entries=[f"*{target}# is NOT a page here.", "", "Try *1# for the index."],
            home=Shortcut(HOME_KEY, INDEX, says="index, or key another page"),
        ).build(address)
    """

    rows_per_entry = 1
    numbered = False

    def draw(self, row: RowWriter, entry: str, digit: str | None) -> None:
        del digit  # a notice numbers nothing
        if entry:
            row.text(fitted(entry, COLUMNS - 1), Colour.WHITE)


class Prose(RowTemplate[Row]):
    """Running text, wrapped and divided between as many frames as it takes.

    Its entries are rendered `Row` values rather than `Entry` values, which is
    what the base class is generic for. Use `Prose.of` to make a page from
    plain paragraphs, or construct it directly with rows from
    `viewdata.typesetting`.

    Laying the text out through `viewdata.typesetting` gives a notice the same
    treatment as a forum post: quotations in cyan, listings in green, nesting
    indented, and over-long words broken rather than dropped. Before this,
    notice pages held string literals hand-broken at forty columns, with empty
    strings for the gaps between paragraphs, which had to be redone by hand
    whenever a word changed and could not survive a change of column width.
    """

    rows_per_entry = 1
    numbered = False

    @classmethod
    def of(
        cls,
        *paragraphs: str,
        title: str,
        home: PageAddress | None = None,
        preamble: Sequence[PreambleLine] = (),
        empty: str = "",
        shortcuts: Sequence[Shortcut] = (),
    ) -> "Prose":
        """Build a template from plain paragraphs, wrapping them on the way.

        Args:
            *paragraphs: The text, one string a paragraph, in the order it is
                to be read. Empty strings are dropped; the gaps between
                paragraphs come from the layout.
            title: The heading drawn at the top of every frame.
            home: Where `0` leads from every frame, or None to offer no way
                home.
            preamble: Lines drawn above the text on the first frame only.
            empty: Text drawn in place of the paragraphs when there are none.
            shortcuts: Keys offered on every frame, besides `0`.

        Returns:
            A template ready for `build`.

        Example::

            Prose.of(
                "The board is read-only here.",
                "Posting is done from the web.",
                title="ABOUT",
                home=INDEX,
            ).build(address)
        """
        return cls(
            title=title,
            entries=rows_for(
                Document(blocks=tuple(Paragraph((text,)) for text in paragraphs if text))
            ),
            home=home,
            preamble=preamble,
            empty=empty,
            shortcuts=shortcuts,
        )

    def draw(self, row: RowWriter, entry: Row, digit: str | None) -> None:
        del digit  # prose numbers nothing
        if entry.text:
            #  No truncation here: `layout` has already wrapped to the room a
            #  row has, colour attribute and indent included. Cutting again
            #  would take a character off every line it had filled exactly.
            row.skip(entry.indent).text(entry.text, entry.colour)


def farewell_page(title: str, *lines: str, hang_up: bool = True) -> Page:
    """Build the page a caller sees last: no chrome, and room beneath to type.

    Args:
        title: The heading, drawn in cyan on the first row.
        *lines: What to say, one string a row, beginning two rows below the
            title. Empty strings leave a blank row.
        hang_up: Whether the line drops once this page has been shown. Pass
            False for the involuntary parting, an idle caller being released,
            where the session drops the line itself.

    Returns:
        A page of a single frame, offering no keys.

    A footer offering the index would be a lie on a page there is no coming
    back from, and the rows it and the rules would take up are exactly the ones
    worth leaving blank: the reader is about to be talking to their modem, and
    the cursor sits below the last thing said.
    """
    canvas = Canvas()
    canvas.row(0).text(title, Colour.CYAN)
    for offset, line in enumerate(lines):
        if line:
            canvas.row(2 + offset).text(fitted(line, COLUMNS - 1), Colour.WHITE)
    return Page(frames=(PageFrame(frame=canvas.frame),), hang_up=hang_up)


def _rows_of(line: PreambleLine) -> int:
    """Rows one preamble line occupies. Everything but a `Block` occupies one."""
    return line.rows if isinstance(line, Block) else 1


def _last_content_row() -> int:
    return CONTENT_FIRST_ROW + CONTENT_ROWS




