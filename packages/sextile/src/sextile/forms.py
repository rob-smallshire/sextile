"""A field on a frame that a reader types into.

Everything else in this framework answers a keypress by going somewhere. A form
answers one by *changing what is on the screen without moving* -- which is the
one thing viewdata pages historically could not do, and the reason Prestel's
response frames were a separate mechanism bolted on beside the numbering.

The shape is deliberately narrow. A form owns some rows of a frame, says which
keys are typing rather than navigating, redraws its rows when the value changes,
and says where its digits lead as the value now stands. The session does the
rest: it keeps the frame in step, sends the changed rows, and treats a digit
that leads somewhere exactly as it treats a digit on a menu -- so history,
sequences and the back key all go on working with nothing added.

**Type-ahead is a menu whose choices change as you type.** That is why so little
is needed here: `PageFrame.choices` already means "what the digits do on this
frame", and a form only makes it answer differently from one keystroke to the
next.

What the wire affords was measured rather than assumed, on real Commstar in
`docs/spikes/spike_suggestion_block.py`. Three suggestions cost 121 bytes -- a
second at 1200 baud -- and the common keystroke, typing on into a list that has
already settled, costs 40. Nine would cost nearly three seconds a keystroke,
which is why `Suggest` offers three.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from sextile import keys
from sextile.addressing import PageAddress
from sextile.templates import Entry
from sextile.viewdata.canvas import Canvas, RowWriter
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import fitted
from sextile.viewdata.frame import COLUMNS, Frame

#: What a form asks to find out what to offer. Given what has been typed so
#: far, it answers whatever should be listed beneath the field.
type Lookup = Callable[[str], Awaitable[Sequence[Entry]]]

#: As many suggestions as the wire affords at 1200 baud. Measured, not chosen.
SUGGESTIONS: Final = 3

#: How a field is marked out. The command line's colours, because a reader
#: should have to learn "this is where typing goes" exactly once -- and because
#: there is no alpha black, so light on dark is the only pairing the hardware
#: offers.
FIELD_BACKGROUND: Final = Colour.BLUE
FIELD_COLOUR: Final = Colour.WHITE

#: What a background costs: the colour, making it the background, and the
#: colour of what is written on it.
_BACKGROUND_CELLS: Final = 3

#: And what ending one costs, which is what bounds a field to its own width.
_END_CELLS: Final = 1

#: What a reader keys to choose the nth suggestion. Digits, as every viewdata
#: menu uses, so nothing new has to be learned.
_FIRST_DIGIT: Final = 1

#: What a mark costs: its colour, a space before it, and the character.
_MARK_CELLS: Final = 3

#: Set at the end of whichever suggestion RETURN would take, in the same colour
#: as the digits, so it reads as a key rather than as decoration.
#:
#: A browser's address bar marks the row that ENTER would choose, and for the
#: same reason: a key that does something invisible is a key nobody presses.
#: Marking it here rather than in the footer puts the answer beside the
#: question -- and gives the footer back the room to say what the other keys do
#: in words.
#:
#: At the *end* of the entry. In front of the digit it abutted it, and `#1`
#: reads as "number 1" rather than as two keys that do the same thing.
SUBMIT_MARK: Final = keys.CONVENTIONAL_NEXT_FRAME

#: A hint is advice and a note is a finding, and they are not the same thing to
#: a reader: the advice under a field says the same words on every frame and is
#: read once, where the note is the service's answer to what has just been
#: typed and is the most interesting thing on the page. Two colours, or the
#: answer sits in a block of instructions and reads as more instruction.
HINT_COLOUR: Final = Colour.GREEN
NOTE_COLOUR: Final = Colour.CYAN


class Form(ABC):
    """Rows of a frame that answer keypresses by redrawing themselves."""

    @property
    @abstractmethod
    def rows(self) -> range:
        """Which rows of the frame this form owns.

        Only these are compared and redrawn, so a form cannot disturb the page
        around it however wrong it is about its own contents.
        """

    @property
    @abstractmethod
    def caret(self) -> tuple[int, int]:
        """Where the cursor goes after a repaint, as (row, column).

        The reader is in the middle of a word. Every frame begins by hiding the
        cursor, and a field is the one place on a service where it tells them
        something.
        """

    @abstractmethod
    def accepts(self, key: str) -> bool:
        """Whether this key is typing rather than navigating.

        Asked *after* the frame's choices have been consulted, so a digit that
        leads somewhere is a selection and never a character.
        """

    @abstractmethod
    async def typed(self, key: str) -> None:
        """Take a key this form accepts, and change accordingly.

        May go to a database or a network: a suggestion list is a query. It is
        awaited on the connection's own task, so a slow one delays this caller
        and no other.
        """

    @abstractmethod
    def draw(self, canvas: Canvas) -> None:
        """Draw this form's rows as they now stand."""

    def choices(self) -> Mapping[str, PageAddress]:
        """Where this form's digits lead, as the value now stands.

        Empty unless a form says otherwise: a field that only collects text
        offers nothing to select.
        """
        return {}

    def submit(self) -> PageAddress | None:
        """Where RETURN leads, or None if there is nowhere to send the reader.

        A reader who has typed something will press RETURN without being told
        to, so a field that did nothing with it would feel broken. The default
        is the first thing on offer -- the same as pressing 1 -- because the
        reader can *see* that list, and refusing something visibly on offer
        because it is not character-for-character what they typed would be
        perverse.

        None where nothing is on offer. The page will already be saying so
        where the suggestions would be, and taking the reader somewhere is
        worse than leaving them to correct what they typed.
        """
        return next(iter(self.choices().values()), None)


class Suggest(Form):
    """A field, and the best few matches for what is in it.

    The shape a viewdata reader already knows -- a short numbered list, chosen
    with one keypress -- with the list changing as they type instead of being
    given a page at a time.

    Letters type. Digits choose. That means a place whose name contains a digit
    cannot be keyed, which is a real limitation and the right trade: a service
    holding such names should fold the digits out of what it matches against,
    so the place is still found by the letters around it.
    """

    def __init__(
        self,
        *,
        look_up: Lookup,
        field_row: int,
        first_row: int,
        label: str = "",
        limit: int = SUGGESTIONS,
        empty: str = "",
        field: Colour = FIELD_BACKGROUND,
        typing: Colour = FIELD_COLOUR,
    ) -> None:
        """Set up the field, its label, and the list of suggestions beneath it.

        Args:
            look_up: Awaited with what has been typed, returning the entries to
                suggest.
            field_row: The row the field itself occupies.
            first_row: The row the suggestions begin on.
            label: Drawn before the field. It should not end in a space: the
                colour attribute that follows it occupies a cell and shows as
                one already.
            limit: The most suggestions to offer at once.
            empty: Said where something has been typed and nothing matched it.
            field: The background colour of the field.
            typing: The colour of what the reader has typed.
        """
        self._look_up = look_up
        self._field_row = field_row
        self._first_row = first_row
        self._label = label
        self._limit = limit
        self._empty = empty
        self._field = field
        self._typing = typing
        self._value = ""
        self._found: Sequence[Entry] = ()

    @property
    def value(self) -> str:
        """What has been typed so far."""
        return self._value

    @property
    def found(self) -> Sequence[Entry]:
        """What is being offered, as the value now stands."""
        return self._found

    @property
    def rows(self) -> range:
        return range(self._field_row, self._first_row + self._limit)

    @property
    def caret(self) -> tuple[int, int]:
        #  Counting the attributes, because each occupies a cell: one before
        #  the label and one before the value. Without them the caret sits two
        #  cells to the left of where the next letter actually lands, which on
        #  the one row of a service where the cursor means anything is exactly
        #  the wrong place for it.
        return self._field_row, self._field_column + len(self._value)

    @property
    def _field_column(self) -> int:
        """The column the typed value starts at, attributes included.

        The label costs its own colour; the field costs three, a background
        being taken from a foreground.
        """
        return (len(self._label) + 1 if self._label else 0) + _BACKGROUND_CELLS

    def accepts(self, key: str) -> bool:
        #  Anything printable except a digit, and the rub-out. Digits are
        #  spoken for by the suggestions, and are never asked about here: the
        #  session consults `choices` first, and one that leads nowhere does
        #  nothing rather than becoming a character whose effect the reader
        #  cannot see.
        #
        #  Spaces and hyphens are taken because place names hold them --
        #  NEW YORK, STRATFORD-UPON-AVON -- and a reader should be able to
        #  type the name as it is written. What they are matched against
        #  folds both out, so accepting them costs nothing and saves somebody
        #  wondering why their space bar is dead.
        return key == keys.RUB_OUT or (
            len(key) == 1 and key.isprintable() and not key.isdigit()
        )

    async def typed(self, key: str) -> None:
        if key == keys.RUB_OUT:
            self._value = self._value[:-1]
        else:
            self._value += key.upper()
        #  Nothing typed is nothing offered, rather than the whole world in
        #  whatever order the index happens to hold it: a reader who has typed
        #  nothing has asked nothing.
        self._found = await self._look_up(self._value) if self._value else ()

    def choices(self) -> Mapping[str, PageAddress]:
        return {
            str(_FIRST_DIGIT + offset): entry.destination
            for offset, entry in enumerate(self._found[: self._limit])
            if entry.destination is not None
        }

    def draw(self, canvas: Canvas) -> None:
        field = canvas.row(self._field_row)
        if self._label:
            field.text(self._label, Colour.CYAN)
        #  A bar of colour to the end of the row, so a reader can see where
        #  typing goes and how much room is left for it. The same marking the
        #  command line has always used for the one other place on a service
        #  that takes typing, so a reader learns it once.
        #
        #  No space is written between the label and the value either: the
        #  attributes occupy cells and show as spaces already.
        field.background(self._field, text=self._typing)
        field.text(fitted(self._value, field.remaining), self._typing)
        for offset in range(self._limit):
            row = canvas.row(self._first_row + offset)
            if offset < len(self._found):
                self._draw_one(row, offset, self._found[offset])
            elif offset == 0 and self._value and self._empty:
                #  Said rather than shown blank: on a service that answers
                #  slowly a reader cannot tell nothing-found from not-answered.
                row.text(fitted(self._empty, COLUMNS - 1), Colour.WHITE)

    #: Cells the name is given before the detail begins. A *fixed* column
    #: rather than one fitted to the widest name showing, for two reasons. A
    #: fitted column moves as the reader types, which turns every keystroke
    #: into a repaint of all three rows; and aligning the detail against the
    #: row's right-hand edge instead makes every row near-full-width, which
    #: costs 1.4 seconds a keystroke at 1200 baud against 0.7 for this.
    _NAME_CELLS: Final = 20

    #: Most of what is left that the detail may take, so a long one cannot
    #: squeeze out the name it is there to qualify.
    _DETAIL_SHARE: Final = 2

    def _draw_one(self, row: RowWriter, offset: int, entry: Entry) -> None:
        row.text(f"{_FIRST_DIGIT + offset} ", Colour.YELLOW)
        detail = fitted(entry.detail, (row.remaining - 2) // self._DETAIL_SHARE)
        name = fitted(entry.text, min(self._NAME_CELLS, row.remaining - 1))
        row.text(name, Colour.WHITE)
        if detail:
            #  Padded to the column rather than written straight after the
            #  name, so the second column is a column whatever the names do.
            row.skip(max(self._NAME_CELLS - len(name), 0))
            row.text(detail, Colour.GREEN)
        #  At the end of the entry rather than in front of the digit, where a
        #  mark and a 1 run together and read as "number 1" instead of as two
        #  keys that do the same thing.
        marked = entry.destination is not None and entry.destination == self.submit()
        if marked and row.remaining > _MARK_CELLS:
            row.text(f" {SUBMIT_MARK}", Colour.YELLOW)


def draw_form(frame: Frame, form: Form) -> None:
    """Redraw a form's own rows onto a frame, leaving the rest of it alone.

    Its rows are blanked first, so what a shorter suggestion vacates does not
    stay behind under a digit that now means something else.
    """
    canvas = Canvas(frame)
    for row in form.rows:
        frame.write(row, 0, " " * COLUMNS)
    form.draw(canvas)


@dataclass
class Field:
    """One place on a frame that a reader types into."""

    name: str
    """What the form calls it when it hands the values over."""

    label: str
    """Shown before it. Should not end in a space: the attributes that follow
    occupy cells and show as spaces already."""

    row: int

    takes: Callable[[str], bool]
    """Whether a character belongs in this field. A form knows about typing;
    what a *latitude* is made of is the service's business."""

    width: int = 12
    """Cells the value may take, after the label and the attributes."""

    hint: str = ""
    """What this field takes, said beneath it and always.

    Said beneath its own field rather than in one place that changes with the
    caret, which is what this was first: a hint that changes is a row that
    repaints on every TAB, and on a form of two fields the rows are there to
    spare. Standing still it costs nothing to move about, and a reader can read
    both before deciding which field to start in.
    """

    hint_row: int | None = None

    value: str = ""


#: Given what has been keyed into each field, where the reader should be sent
#: -- or None while there is nowhere to send them.
#:
#: Asked whenever the form is drawn, not only when RETURN is pressed, because
#: what RETURN would do is marked on the screen and a mark that promised a page
#: which then did not arrive would be worse than no mark. So it is asked of
#: half-keyed forms and empty ones, and must answer rather than raise.
type Complete = Callable[[Mapping[str, str]], PageAddress | None]

#: Something to say about what has been keyed so far, drawn beneath the fields.
type Note = Callable[[Mapping[str, str]], Awaitable[str]]


class Fields(Form):
    """Several fields, one of them live, and something said beneath them.

    The interaction is settled by what a viewdata keypad can send, and it is
    narrower than it looks. Two of the four arrows are unusable on a form whose
    fields hold compass letters -- up arrives as `W` for West and down as `S`
    for South -- so the framework no longer translates them at all and this
    reads them as arrows. TAB shares a byte with cursor right, measured against
    Commstar, which is the key a reader will reach for first.

    And `0` cannot be the way out where digits are data, so a page carrying one
    of these should say `*1#` in its footer rather than offer a key that would
    type a zero.

    Nothing advances by itself. A field that jumped to the next when it thought
    it had enough would be a field whose caret is somewhere the reader did not
    put it -- and with two ways of writing a coordinate, one of them ending in
    a letter and one not, it could not even be consistent about when.
    """

    #: Forward, and back. TAB is cursor right on this hardware.
    _ONWARD: Final = frozenset({keys.RIGHT, keys.DOWN})
    _BACK: Final = frozenset({keys.LEFT, keys.UP})

    def __init__(
        self,
        *,
        fields: Sequence[Field],
        complete: Complete,
        note: Note | None = None,
        note_row: int | None = None,
        sends: str = "",
        field: Colour = FIELD_BACKGROUND,
        typing: Colour = FIELD_COLOUR,
    ) -> None:
        if not fields:
            raise ValueError("a form needs a field to type into")
        self._fields = list(fields)
        self._complete = complete
        self._note = note
        self._note_row = note_row
        #: What finishing the form does, in a word, shown against the key that
        #: does it. Empty for a form whose last field is self-explanatory.
        self._sends = sends
        self._field = field
        self._typing = typing
        self._live = 0
        self._said = ""

    @property
    def values(self) -> Mapping[str, str]:
        """What has been keyed into each field, by name."""
        return {field.name: field.value for field in self._fields}

    @property
    def live(self) -> Field:
        """The field the caret is in."""
        return self._fields[self._live]

    @property
    def rows(self) -> range:
        rows = [field.row for field in self._fields]
        rows += [field.hint_row for field in self._fields if field.hint_row is not None]
        if self._note_row is not None:
            rows.append(self._note_row)
        return range(min(rows), max(rows) + 1)

    @property
    def caret(self) -> tuple[int, int]:
        return self.live.row, self._column_of(self.live) + len(self.live.value)

    def accepts(self, key: str) -> bool:
        return (
            key in self._ONWARD
            or key in self._BACK
            or key == keys.RUB_OUT
            or self.live.takes(key)
        )

    async def typed(self, key: str) -> None:
        if key in self._ONWARD:
            #  Round, not up to the end and no further. A reader who tabs into
            #  the last field and wants the first back has nowhere else to go:
            #  the back arrows are there, but nobody who has just learned that
            #  TAB moves on will think to look for them.
            self._live = (self._live + 1) % len(self._fields)
        elif key in self._BACK:
            self._live = (self._live - 1) % len(self._fields)
        elif key == keys.RUB_OUT:
            self.live.value = self.live.value[:-1]
        elif len(self.live.value) < self.live.width:
            self.live.value += key.upper()
        if self._note is not None:
            self._said = await self._note(self.values)

    def submit(self) -> PageAddress | None:
        """Onward, and away from the last.

        RETURN on a form is the same key as RETURN on a terminal has always
        been: it finishes the field you are in. On the last one there is
        nothing left to finish, so it finishes the form.

        Which is why it does not cycle where TAB does. TAB moves about a form;
        RETURN gets to the end of one.
        """
        if self._live + 1 < len(self._fields):
            self._live += 1
            return None
        return self._complete(self.values)

    def draw(self, canvas: Canvas) -> None:
        for offset, field in enumerate(self._fields):
            row = canvas.row(field.row)
            #  Labels padded to the widest, so the values line up as a column
            #  rather than each starting wherever its own label happened to end.
            row.text(field.label.ljust(self._widest), Colour.CYAN)
            if offset == self._live:
                #  The live field is marked out and the others are not. A caret
                #  alone would say which, and a caret is one cell of nine
                #  hundred.
                row.background(self._field, text=self._typing)
                #  The bar is exactly the field's width, padded and then ended.
                #  A background runs to the end of the row unless something
                #  stops it, which would say there is room for thirty
                #  characters in a field that takes six.
                room = min(field.width, row.remaining - _END_CELLS)
                row.text(fitted(field.value, room).ljust(room), self._typing)
                row.plain()
            else:
                #  Two spaces and the colour attribute before them come to the
                #  three cells a background costs, so a field does not shift
                #  sideways when the caret arrives in it.
                row.text(f"  {fitted(field.value, field.width)}", Colour.WHITE)
            self._mark_sending(row, offset)
            if field.hint_row is not None and field.hint:
                canvas.row(field.hint_row).text(
                    fitted(field.hint, COLUMNS - 1), HINT_COLOUR
                )
        if self._note_row is not None and self._said:
            canvas.row(self._note_row).text(
                fitted(self._said, COLUMNS - 1), NOTE_COLOUR
            )

    def _mark_sending(self, row: RowWriter, offset: int) -> None:
        """Say what RETURN does, beside the field where it does it.

        Only the last one. On any other, RETURN moves to the next field --
        which is what TAB does, and what the footer already says -- so marking
        it there would be naming a key twice for one job. On the last there is
        nothing left to finish, so it finishes the form, and that is worth
        saying where the reader is looking rather than at the foot of the
        frame.

        And only while there is somewhere to send them. A page that offered to
        go somewhere and then did nothing would be worse than one that offered
        nothing: on a slow line a reader cannot tell a dead key from a slow
        one.
        """
        if offset + 1 != len(self._fields) or self._complete(self.values) is None:
            return
        said = f" {SUBMIT_MARK} {self._sends}".rstrip()
        if row.remaining > len(said):
            row.text(said, Colour.YELLOW)

    @property
    def _widest(self) -> int:
        """The widest label, which every value is set after."""
        return max(len(field.label) for field in self._fields)

    def _column_of(self, field: Field) -> int:
        """Where a field's value starts, attributes counted.

        The label costs its colour and the field costs three, a background
        being taken from a foreground. The same for every field, live or not,
        which is what stops one moving under the reader.
        """
        del field
        return self._widest + 1 + _BACKGROUND_CELLS
