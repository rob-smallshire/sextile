"""The form contract: rows of a frame that answer keypresses by redrawing.

`Form` is the base every field type subclasses, and `draw_form` repaints one
onto a frame. The shape a form must satisfy is deliberately narrow: it owns some
rows, says which keys are typing rather than navigating, redraws its rows when
the value changes, and says where its digits lead as the value now stands. The
session does the remainder.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Final

from sextile import keys
from sextile.formatting import Entry
from sextile.layout import Claim, Placed, Space
from sextile.layout.footer import FooterItem
from sextile.page import PageAddress
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.controls import Colour
from sextile.viewdata.frame import COLUMNS, Frame

#: What a form asks to find out what to offer. Given what has been typed so
#: far, it answers whatever should be listed beneath the field.
type Lookup = Callable[[str], Awaitable[Sequence[Entry]]]

#: How a field is marked out. The command line's colours, because a reader
#: should have to learn "this is where typing goes" exactly once -- and because
#: there is no alpha black, so light on dark is the only pairing the hardware
#: offers.
FIELD_BACKGROUND: Final = Colour.BLUE
FIELD_COLOUR: Final = Colour.WHITE

#: What a background costs: the colour, making it the background, and the
#: colour of what is written on it. Shared by both field types, which each
#: start their value after the attributes so it does not shift as the caret
#: arrives.
_BACKGROUND_CELLS: Final = 3

#: Set at the end of whichever entry RETURN would take, in the same colour as
#: the digits, so it reads as a key rather than as decoration.
#:
#: A browser's address bar marks the row that ENTER would choose, and for the
#: same reason: a key that does something invisible is a key nobody presses.
#: Marking it here rather than in the footer puts the answer beside the
#: question -- and gives the footer back the room to say what the other keys do
#: in words.
#:
#: At the *end* of the entry. In front of the digit it abutted it, and `#1`
#: reads as "number 1" rather than as two keys that do the same thing.
SUBMIT_MARK: Final = keys.HASH


class Form(ABC):
    """Rows of a frame that answer keypresses by redrawing themselves.

    A form is a `layout.Drawable`, and the one that is not a description: it
    holds what has been typed, so a layout carrying one is built for the
    request it answers rather than kept and built again.

    A subclass numbers its rows from nought, and `top_row` is where the layout put
    it. Everything a form draws or reports is offset by that, so a form need not
    track where the content of a frame begins.
    """

    #: The row this form was placed on. Nought until it has been.
    top_row: int = 0

    def place(self, canvas: "Canvas", space: "Space") -> "Placed":
        """Draw this form where the layout has put it, and claim its keys.

        Args:
            canvas: The frame being filled.
            space: What the frame has left to give.

        Returns:
            The rows it took, the digits its suggestions answer to, and itself
            as the frame's form. A form is drawn whole or not at all, so a
            frame without room for it is asked to begin another.
        """
        self.top_row = space.first_row
        if len(self.rows) > space.rows:
            return Placed(rows=0, remainder=self)
        self.draw(canvas)
        return Placed(
            rows=len(self.rows),
            claim=Claim(choices=self.choices(), named=self.footer_items(), form=self),
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

    def footer_items(self) -> Sequence[FooterItem]:
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


def draw_form(frame: Frame, form: Form) -> None:
    """Redraw a form's own rows onto a frame, leaving the rest of it alone.

    Its rows are blanked first, so what a shorter suggestion vacates does not
    stay behind under a digit that now means something else.
    """
    canvas = Canvas(frame)
    for row in form.rows:
        frame.write(row, 0, " " * COLUMNS)
    form.draw(canvas)
