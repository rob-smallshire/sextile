"""A field, and the best few matches for what is in it, updating as you type.

**Type-ahead is a menu whose choices change as you type.** That is why so little
is needed for it: `PageFrame.choices` already means "what the digits do on this
frame", and this only makes it answer differently from one keystroke to the
next.

What the wire affords was measured rather than assumed, on real Commstar in
`docs/spikes/spike_suggestion_block.py`. Three suggestions cost 121 bytes -- a
second at 1200 baud -- and the common keystroke, typing on into a list that has
already settled, costs 40. Nine would cost nearly three seconds a keystroke,
which is why `TypeAhead` offers three.
"""

from collections.abc import Mapping, Sequence
from typing import Final

from sextile import keys
from sextile.formatting import Entry
from sextile.forms.base import (
    _BACKGROUND_CELLS,
    FIELD_BACKGROUND,
    FIELD_COLOUR,
    SUBMIT_MARK,
    Form,
    Lookup,
)
from sextile.layout.footer import FooterItem, Priority
from sextile.page import PageAddress
from sextile.viewdata.canvas import Canvas, RowWriter
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import COLUMNS
from sextile.viewdata.measure import fitted

#: As many suggestions as the wire affords at 1200 baud. Measured, not chosen.
SUGGESTIONS: Final = 3

#: What a reader keys to choose the nth suggestion. Digits, as every viewdata
#: menu uses, so nothing new has to be learned.
_FIRST_DIGIT: Final = 1

#: What a mark costs: its colour, a space before it, and the character.
_MARK_CELLS: Final = 3


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
        return range(
            self.top_row + self._field_row,
            self.top_row + self._suggestions_row + self._limit,
        )

    @property
    def caret(self) -> tuple[int, int]:
        #  Counting the attributes, because each occupies a cell: one before
        #  the label and one before the value. Without them the caret sits two
        #  cells to the left of where the next letter actually lands, which on
        #  the one row of a service where the cursor means anything is exactly
        #  the wrong place for it.
        return self.top_row + self._field_row, self._field_column + len(self._value)

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

    def footer_items(self) -> Sequence[FooterItem]:
        #  Only the digits: that a field is typed into is plain from the block
        #  of colour with the cursor in it, so a word saying so would spend
        #  footer room on what the reader can see. What `#` does is marked
        #  against the suggestion it would take, which is where a reader is
        #  looking anyway. The digits named are the ones on offer -- two matches
        #  say `1-2`, one says `1` -- and where nothing has been typed the field
        #  says how many it can offer, the footer being drawn once, with an
        #  empty field, so a bare count would say nothing of the choice to come.
        offered = len(self.choices()) or self._limit
        keyed = "1" if offered == 1 else f"1-{offered}"
        return (FooterItem(keyed, "choose one", Priority.PRIMARY),)

    def choices(self) -> Mapping[str, PageAddress]:
        return {
            str(_FIRST_DIGIT + offset): entry.destination
            for offset, entry in enumerate(self._found[: self._limit])
            if entry.destination is not None
        }

    def draw(self, canvas: Canvas) -> None:
        field = canvas.row(self.top_row + self._field_row)
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
        #  The row RETURN takes, by position rather than by destination: it is
        #  the first suggestion a digit leads anywhere, which is what `submit`
        #  returns. Comparing destinations instead marks every row that shares
        #  the first one's, and suggestions may legitimately share a page.
        marked_offset = next(
            (
                offset
                for offset, entry in enumerate(self._found[: self._limit])
                if entry.destination is not None
            ),
            None,
        )
        for offset in range(self._limit):
            row = canvas.row(self.top_row + self._suggestions_row + offset)
            if offset < len(self._found):
                self._draw_one(row, offset, self._found[offset], marked=offset == marked_offset)
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

    def _draw_one(self, row: RowWriter, offset: int, entry: Entry, *, marked: bool) -> None:
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
        if marked and row.remaining > _MARK_CELLS:
            row.text(f" {SUBMIT_MARK}", Colour.YELLOW)
