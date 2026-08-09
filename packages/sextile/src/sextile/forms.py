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
from typing import Final

from sextile import keys
from sextile.addressing import PageAddress
from sextile.templates import Entry
from sextile.viewdata.canvas import Canvas, RowWriter
from sextile.viewdata.controls import Colour
from sextile.viewdata.drawing import fitted
from sextile.viewdata.frame import COLUMNS, Frame

#: What a form asks to find out what to offer. Given what has been typed so
#: far, it answers whatever should be listed beneath the field.
type Lookup = Callable[[str], Awaitable[Sequence[Entry]]]

#: As many suggestions as the wire affords at 1200 baud. Measured, not chosen.
SUGGESTIONS: Final = 3

#: What a reader keys to choose the nth suggestion. Digits, as every viewdata
#: menu uses, so nothing new has to be learned.
_FIRST_DIGIT: Final = 1


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


class Suggest(Form):
    """A field, and the best few matches for what is in it.

    The shape a viewdata reader already knows -- a short numbered list, chosen
    with one keypress -- with the list changing as they type instead of being
    dealt a page at a time.

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
    ) -> None:
        """``label`` should not end in a space: the colour attribute that
        follows it occupies a cell and shows as one already."""
        self._look_up = look_up
        self._field_row = field_row
        self._first_row = first_row
        self._label = label
        self._limit = limit
        self._empty = empty
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
        """The column the typed value starts at, attributes included."""
        return (len(self._label) + 1 if self._label else 0) + 1

    def accepts(self, key: str) -> bool:
        #  Letters and the rub-out. Digits are spoken for by the suggestions,
        #  and are never asked about here: the session consults `choices`
        #  first, and a digit that leads nowhere does nothing rather than
        #  becoming a character the reader cannot see the effect of.
        return key == keys.RUB_OUT or (len(key) == 1 and key.isalpha())

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
        #  No space is written between the label and the value: the colour
        #  attribute before the value occupies a cell and shows as one. A
        #  label ending in a space would therefore read with two.
        field.text(fitted(self._value, field.remaining - 1), Colour.YELLOW)
        for offset in range(self._limit):
            row = canvas.row(self._first_row + offset)
            if offset < len(self._found):
                self._draw_one(row, offset, self._found[offset])
            elif offset == 0 and self._value and self._empty:
                #  Said rather than shown blank: on a service that answers
                #  slowly a reader cannot tell nothing-found from not-answered.
                row.text(fitted(self._empty, COLUMNS - 1), Colour.WHITE)

    def _draw_one(self, row: RowWriter, offset: int, entry: Entry) -> None:
        row.text(f"{_FIRST_DIGIT + offset} ", Colour.YELLOW)
        room = row.remaining - 1
        detail = f"  {entry.detail}" if entry.detail else ""
        row.text(fitted(entry.text, room - len(detail)), Colour.WHITE)
        if detail:
            row.text(fitted(detail, row.remaining - 1), Colour.GREEN)


def draw_form(frame: Frame, form: Form) -> None:
    """Redraw a form's own rows onto a frame, leaving the rest of it alone.

    Its rows are blanked first, so what a shorter suggestion vacates does not
    stay behind under a digit that now means something else.
    """
    canvas = Canvas(frame)
    for row in form.rows:
        frame.write(row, 0, " " * COLUMNS)
    form.draw(canvas)
