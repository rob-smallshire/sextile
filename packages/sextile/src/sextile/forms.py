"""A field on a frame that a reader types into.

Everything else in this framework answers a keypress by going somewhere. A form
answers one by *changing what is on the screen without moving*.

The shape is deliberately narrow. A form owns some rows of a frame, says which
keys are typing rather than navigating, redraws its rows when the value changes,
and says where its digits lead as the value now stands. The session does the
remainder: it keeps the frame in step, sends the changed rows, and treats a digit
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
which is why `TypeAhead` offers three.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from sextile import keys
from sextile.addressing import PageAddress
from sextile.formatting import Entry
from sextile.layout import Claim, Placed, Space
from sextile.viewdata.canvas import Canvas, RowWriter
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import fitted
from sextile.viewdata.footer import FooterItem, Priority
from sextile.viewdata.frame import COLUMNS, Frame

__all__ = [
    "Complete",
    "Field",
    "Fields",
    "Form",
    "Lookup",
    "Note",
    "SUGGESTIONS",
    "TypeAhead",
    "draw_form",
]

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
    """Rows of a frame that answer keypresses by redrawing themselves.

    A form is a `layout.Drawable`, and the one that is not a description: it
    holds what has been typed, so a layout carrying one is built for the
    request it answers rather than kept and built again.

    A subclass numbers its rows from nought, and `at` is where the layout put
    it. Everything a form draws or reports is offset by that, so a form need not
    track where the content of a frame begins.
    """

    #: The row this form was placed on. Nought until it has been.
    at: int = 0

    def place(self, canvas: "Canvas", room: "Space") -> "Placed":
        """Draw this form where the layout has put it, and claim its keys.

        Args:
            canvas: The frame being filled.
            room: What the frame has left to give.

        Returns:
            The rows it took, the digits its suggestions answer to, and itself
            as the frame's form. A form is drawn whole or not at all, so a
            frame without room for it is asked to begin another.
        """
        self.at = room.first_row
        if len(self.rows) > room.rows:
            return Placed(rows=0, remainder=self)
        self.draw(canvas)
        return Placed(
            rows=len(self.rows),
            claim=Claim(choices=self.choices(), named=self.named(), form=self),
        )

    @property
    @abstractmethod
    def rows(self) -> range:
        """Which rows of the frame this form owns, once it has been placed.

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

    def named(self) -> Sequence[FooterItem]:
        """What the prompt should say about the keys this form answers.

        Empty unless a form says otherwise. A form is the only part that
        answers letters, so it is the only one that has to explain them.
        """
        return ()

    def submit(self) -> PageAddress | None:
        """Where RETURN leads, or None if there is nowhere to send the reader.

        A reader who has typed something presses RETURN without being told to,
        so the default is the first thing on offer -- the same as pressing 1 --
        which the reader can see. Refusing something visibly on offer because it
        is not character-for-character what was typed would surprise them.

        None where nothing is on offer. The page already says so where the
        suggestions would be, and moving the reader is worse than leaving them
        to correct what they typed.
        """
        return next(iter(self.choices().values()), None)


class TypeAhead(Form):
    """A field, and the best few matches for what is in it.

    The shape a viewdata reader already knows -- a short numbered list, chosen
    with one keypress -- with the list changing as they type instead of being
    given a page at a time.

    Letters type. Digits choose. That means an entry whose text contains a digit
    cannot be keyed, which is a real limitation and the right trade: a service
    with such entries should fold the digits out of what it matches against, so
    the entry is still found by the letters around it.
    """

    def __init__(
        self,
        *,
        lookup: Lookup,
        field_row: int = 0,
        suggestions_row: int = 2,
        label: str = "",
        limit: int = SUGGESTIONS,
        no_match: str = "",
        field_colour: Colour = FIELD_BACKGROUND,
        text_colour: Colour = FIELD_COLOUR,
    ) -> None:
        """Set up the field, its label, and the list of suggestions beneath it.

        Args:
            lookup: Awaited with what has been typed, returning the entries to
                suggest.
            field_row: The row the field itself occupies.
            suggestions_row: The row the suggestions begin on.
            label: Drawn before the field. It should not end in a space: the
                colour attribute that follows it occupies a cell and shows as
                one already.
            limit: The most suggestions to offer at once.
            no_match: Said where something has been typed and nothing matched it.
            field_colour: The background colour of the field.
            text_colour: The colour of what the reader has typed.
        """
        self._lookup = lookup
        self._field_row = field_row
        self._suggestions_row = suggestions_row
        self._label = label
        self._limit = limit
        self._no_match = no_match
        self._field_colour = field_colour
        self._text_colour = text_colour
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
        return range(self.at + self._field_row, self.at + self._suggestions_row + self._limit)

    @property
    def caret(self) -> tuple[int, int]:
        #  Counting the attributes, because each occupies a cell: one before
        #  the label and one before the value. Without them the caret sits two
        #  cells to the left of where the next letter actually lands, which on
        #  the one row of a service where the cursor means anything is exactly
        #  the wrong place for it.
        return self.at + self._field_row, self._field_column + len(self._value)

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
        #  Spaces and hyphens are taken because a name a reader types may hold
        #  them, and they should be able to type it as it is written. What the
        #  text is matched against can fold both out, so accepting them costs
        #  nothing and saves a reader wondering why their space bar is dead.
        return key == keys.RUB_OUT or (
            len(key) == 1 and key.isprintable() and not key.isdigit()
        )

    async def typed(self, key: str) -> None:
        if key == keys.RUB_OUT:
            self._value = self._value[:-1]
        else:
            self._value += key.upper()
        #  Nothing typed is nothing offered, rather than everything the index
        #  holds in whatever order it happens to hold it: a reader who has typed
        #  nothing has asked nothing.
        self._found = await self._lookup(self._value) if self._value else ()

    def named(self) -> Sequence[FooterItem]:
        #  What `#` does is marked against the suggestion it would take, which
        #  is where a reader is looking anyway, so the row has the room to say
        #  the rest in words. A range rather than a count: with one match on
        #  offer, `1-3` would name two keys that do nothing, and the list
        #  numbers itself where the reader is looking.
        return (
            FooterItem("A-Z", "type a name", Priority.PRIMARY),
            FooterItem("1-9", "choose one", Priority.PRIMARY),
        )

    def choices(self) -> Mapping[str, PageAddress]:
        return {
            str(_FIRST_DIGIT + offset): entry.destination
            for offset, entry in enumerate(self._found[: self._limit])
            if entry.destination is not None
        }

    def draw(self, canvas: Canvas) -> None:
        field = canvas.row(self.at + self._field_row)
        if self._label:
            field.text(self._label, Colour.CYAN)
        #  A bar of colour to the end of the row, so a reader can see where
        #  typing goes and how much room is left for it. The same marking the
        #  command line has always used for the one other place on a service
        #  that takes typing, so a reader learns it once.
        #
        #  No space is written between the label and the value either: the
        #  attributes occupy cells and show as spaces already.
        field.background(self._field_colour, text=self._text_colour)
        field.text(fitted(self._value, field.remaining), self._text_colour)
        for offset in range(self._limit):
            row = canvas.row(self.at + self._suggestions_row + offset)
            if offset < len(self._found):
                self._draw_one(row, offset, self._found[offset])
            elif offset == 0 and self._value and self._no_match:
                #  Said rather than shown blank: on a service that answers
                #  slowly a reader cannot tell nothing-found from not-answered.
                row.text(fitted(self._no_match, COLUMNS - 1), Colour.WHITE)

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
    """Whether a character belongs in this field. A form handles typing; what a
    particular field's value is made of is the service's concern."""

    width: int = 12
    """Cells the value may take, after the label and the attributes."""

    hint: str = ""
    """What this field takes, said beneath it and always.

    Said beneath its own field rather than in one place that changes with the
    caret: a hint that changes is a row that repaints on every TAB, where a
    hint that stands still costs nothing to move about and lets a reader read
    both before deciding which field to start in.
    """

    hint_row: int | None = None

    value: str = ""


#: Given what has been keyed into each field, where the reader should be sent
#: -- or None while there is nowhere to send them.
#:
#: Asked whenever the form is drawn, not only when RETURN is pressed, because
#: what RETURN would do is marked on the screen and the mark must match what
#: RETURN actually does. So it is asked of half-keyed forms and empty ones, and
#: must answer rather than raise.
type Complete = Callable[[Mapping[str, str]], PageAddress | None]

#: Something to say about what has been keyed so far, drawn beneath the fields.
type Note = Callable[[Mapping[str, str]], Awaitable[str]]


class Fields(Form):
    """Several fields, one of them live, and something said beneath them.

    The interaction is settled by what a viewdata keypad can send, and it is
    narrower than it looks. Two of the four arrows are unusable on a form whose
    fields hold the letters `W` and `S` as data -- up arrives as `W` and down as
    `S` -- so the framework does not translate them, and this reads them as
    arrows. TAB shares a byte with cursor right, measured against Commstar, which
    is the key a reader will reach for first.

    And `0` cannot be the way out where digits are data, so a page carrying one
    of these should say `*1#` in its footer rather than offer a key that would
    type a zero.

    Nothing advances by itself. A field that jumped to the next when it judged
    itself full would put the caret where the reader did not, and no single rule
    for "full" fits every field.
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
        advice: Sequence[FooterItem] = (),
        field_colour: Colour = FIELD_BACKGROUND,
        text_colour: Colour = FIELD_COLOUR,
    ) -> None:
        if not fields:
            raise ValueError("a form needs a field to type into")
        #: What else the prompt should say, over and above the keys this form
        #: answers. A page whose fields take digits cannot offer `0` for the
        #: index -- a nought keyed into a numeric field is a nought -- so it says
        #: how to leave some other way.
        self._advice = tuple(advice)
        self._fields = list(fields)
        self._complete = complete
        self._note = note
        self._note_row = note_row
        #: What finishing the form does, in a word, shown against the key that
        #: does it. Empty for a form whose last field is self-explanatory.
        self._sends = sends
        self._field_colour = field_colour
        self._text_colour = text_colour
        self._live = 0
        self._said = ""

    def named(self) -> Sequence[FooterItem]:
        #  Not `#`. It moves to the next field from every field but the last,
        #  so a footer saying "# go there" is false wherever the reader most
        #  likely is. What it does on the last field is marked against that
        #  field, where the reader is looking.
        return (
            FooterItem("TAB", "next field", Priority.PRIMARY),
            FooterItem("DEL", "rub out", Priority.SECONDARY),
            *self._advice,
        )

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
        return range(self.at + min(rows), self.at + max(rows) + 1)

    @property
    def caret(self) -> tuple[int, int]:
        return self.at + self.live.row, self._column_of(self.live) + len(self.live.value)

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
            row = canvas.row(self.at + field.row)
            #  Labels padded to the widest, so the values line up as a column
            #  rather than each starting wherever its own label happened to end.
            row.text(field.label.ljust(self._widest), Colour.CYAN)
            if offset == self._live:
                #  The live field is marked out and the others are not. A caret
                #  alone would say which, and a caret is one cell of nine
                #  hundred.
                row.background(self._field_colour, text=self._text_colour)
                #  The bar is exactly the field's width, padded and then ended.
                #  A background runs to the end of the row unless something
                #  stops it, which would say there is room for thirty
                #  characters in a field that takes six.
                room = min(field.width, row.remaining - _END_CELLS)
                row.text(fitted(field.value, room).ljust(room), self._text_colour)
                row.plain()
            else:
                #  Two spaces and the colour attribute before them come to the
                #  three cells a background costs, so a field does not shift
                #  sideways when the caret arrives in it.
                row.text(f"  {fitted(field.value, field.width)}", Colour.WHITE)
            self._mark_sending(row, offset)
            if field.hint_row is not None and field.hint:
                canvas.row(self.at + field.hint_row).text(
                    fitted(field.hint, COLUMNS - 1), HINT_COLOUR
                )
        if self._note_row is not None and self._said:
            canvas.row(self.at + self._note_row).text(
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
