"""Several fields on a frame, one of them live, and something said beneath them.

`Field` is one place a reader types into; `FieldSet` is a form of several, with
one field live at a time, and reads the arrows and TAB the viewdata keypad can
send. `SubmitHandler` and `Footnote` are what a service passes it: where the
keyed values lead, and what to say about them as they stand.
"""

from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from sextile import keys
from sextile.forms.base import (
    _BACKGROUND_CELLS,
    FIELD_BACKGROUND,
    FIELD_COLOUR,
    SUBMIT_MARK,
    Form,
)
from sextile.layout.footer import FooterItem, Priority
from sextile.page import PageAddress
from sextile.viewdata.canvas import Canvas, RowWriter
from sextile.viewdata.controls import Colour
from sextile.viewdata.encoding import fitted
from sextile.viewdata.frame import COLUMNS

#: And what ending a background costs, which is what bounds a field to its own
#: width.
_END_CELLS: Final = 1

#: A hint is advice and a note is a finding, and they are not the same thing to
#: a reader: the advice under a field says the same words on every frame and is
#: read once, where the note is the service's answer to what has just been
#: typed and is the most interesting thing on the page. Two colours, or the
#: answer sits in a block of instructions and reads as more instruction.
HINT_COLOUR: Final = Colour.GREEN
NOTE_COLOUR: Final = Colour.CYAN


@dataclass
class Field:
    """One place on a frame that a reader types into."""

    name: str
    """What the form calls it when it hands the values over."""

    label: str
    """Shown before it. Should not end in a space: the attributes that follow
    occupy cells and show as spaces already."""

    row: int

    accepts: Callable[[str], bool]
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
type SubmitHandler = Callable[[Mapping[str, str]], PageAddress | None]

#: Something to say about what has been keyed so far, drawn beneath the fields.
type Footnote = Callable[[Mapping[str, str]], Awaitable[str]]


class FieldSet(Form):
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
        on_submit: SubmitHandler,
        footnote: Footnote | None = None,
        footnote_row: int | None = None,
        submit_label: str = "",
        footer_items: Sequence[FooterItem] = (),
        field_colour: Colour = FIELD_BACKGROUND,
        text_colour: Colour = FIELD_COLOUR,
    ) -> None:
        if not fields:
            raise ValueError("a form needs a field to type into")
        #: What else the prompt should say, over and above the keys this form
        #: answers. A page whose fields take digits cannot offer `0` for the
        #: index -- a nought keyed into a numeric field is a nought -- so it says
        #: how to leave some other way.
        self._footer_items = tuple(footer_items)
        self._fields = list(fields)
        self._on_submit = on_submit
        self._footnote = footnote
        self._footnote_row = footnote_row
        #: What finishing the form does, in a word, shown against the key that
        #: does it. Empty for a form whose last field is self-explanatory.
        self._submit_label = submit_label
        self._field_colour = field_colour
        self._text_colour = text_colour
        self._live = 0
        self._said = ""

    def footer_items(self) -> Sequence[FooterItem]:
        #  Not `#`. It moves to the next field from every field but the last,
        #  so a footer saying "# go there" is false wherever the reader most
        #  likely is. What it does on the last field is marked against that
        #  field, where the reader is looking.
        return (
            FooterItem("TAB", "next field", Priority.PRIMARY),
            FooterItem("DEL", "rub out", Priority.SECONDARY),
            *self._footer_items,
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
        if self._footnote_row is not None:
            rows.append(self._footnote_row)
        return range(self.top_row + min(rows), self.top_row + max(rows) + 1)

    @property
    def caret(self) -> tuple[int, int]:
        return self.top_row + self.live.row, self._column_of(self.live) + len(self.live.value)

    def accepts(self, key: str) -> bool:
        return (
            key in self._ONWARD
            or key in self._BACK
            or key == keys.RUB_OUT
            or self.live.accepts(key)
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
        if self._footnote is not None:
            self._said = await self._footnote(self.values)

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
        return self._on_submit(self.values)

    def draw(self, canvas: Canvas) -> None:
        for offset, field in enumerate(self._fields):
            row = canvas.row(self.top_row + field.row)
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
                row.end_background()
            else:
                #  Two spaces and the colour attribute before them come to the
                #  three cells a background costs, so a field does not shift
                #  sideways when the caret arrives in it.
                row.text(f"  {fitted(field.value, field.width)}", Colour.WHITE)
            self._mark_sending(row, offset)
            if field.hint_row is not None and field.hint:
                canvas.row(self.top_row + field.hint_row).text(
                    fitted(field.hint, COLUMNS - 1), HINT_COLOUR
                )
        if self._footnote_row is not None and self._said:
            canvas.row(self.top_row + self._footnote_row).text(
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
        if offset + 1 != len(self._fields) or self._on_submit(self.values) is None:
            return
        said = f" {SUBMIT_MARK} {self._submit_label}".rstrip()
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
