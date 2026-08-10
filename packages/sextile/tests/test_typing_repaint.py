"""Where the cursor ends up after every keystroke of a word.

A form's repaint is a diff, and a diff is only as good as its agreement with
what the terminal actually holds. This follows the bytes we send, works out
where they leave the cursor, and asks whether that is where the form thinks it
is.

The bug it was written for: **a space is a blank cell.** Typing one changes
nothing in the frame, so nothing was sent -- and the cursor stayed where it was
while the form's caret moved on. Everything after that was a cell out: the next
letter landed in the space, and rubbing out took the wrong cell and left
characters behind. Found by typing `ULAN BATOR` into a real service.
"""

from collections.abc import Sequence

import pytest

from sextile import Page, PageAddress, PageFrame, PageRequest, PageRoute, Sextile
from sextile.forms import Suggest, draw_form
from sextile.session.session import Session
from sextile.templates import Entry, MenuItem
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.encoding import ScreenControl
from sextile.viewdata.frame import COLUMNS

FIELD_ROW = 2
FIRST_ROW = 4

PLACES = ["ULAN BATOR", "ULANHOT", "ULLAPOOL", "NEW YORK", "YORK"]


def _folded(text: str) -> str:
    return "".join(letter for letter in text.upper() if letter.isalpha())


async def look_up(typed: str) -> Sequence[Entry]:
    return [
        MenuItem(name.title(), "XX", PageAddress(f"32{1000 + n}"))
        for n, name in enumerate(PLACES)
        if _folded(name).startswith(_folded(typed))
    ]


class Cursor:
    """Enough of a terminal to follow one, and nothing that draws.

    The controls a repaint uses, and the rule a repaint rests on: a printable
    character advances the cursor by one, and a row filled to column forty
    wraps by itself.
    """

    def __init__(self) -> None:
        self.row = 0
        self.column = 0

    def apply(self, sent: bytes | Sequence[bytes]) -> None:
        """Everything a session sends back, which is a list of replies."""
        for byte in sent if isinstance(sent, bytes) else b"".join(sent):
            if byte == ScreenControl.CURSOR_HOME:
                self.row = self.column = 0
            elif byte == ScreenControl.LINE_FEED:
                self.row += 1
            elif byte == ScreenControl.CARRIAGE_RETURN:
                self.column = 0
            elif byte == ScreenControl.CURSOR_LEFT:
                self.column -= 1
            elif byte == ScreenControl.CURSOR_RIGHT:
                self.column += 1
            elif byte == ScreenControl.CURSOR_UP:
                self.row -= 1
            elif byte >= 0x20:
                self.column += 1
                if self.column == COLUMNS:
                    self.row, self.column = self.row + 1, 0

    @property
    def at(self) -> tuple[int, int]:
        return self.row, self.column


async def a_session() -> tuple[Session, Suggest, Cursor]:
    form = Suggest(
        look_up=look_up, field_row=FIELD_ROW, first_row=FIRST_ROW, label="PLACE:"
    )

    async def search(request: PageRequest) -> Page:
        canvas = Canvas()
        draw_form(canvas.frame, form)
        return Page(frames=(PageFrame(frame=canvas.frame, form=form),))

    app = Sextile(pages=[PageRoute("1", search, name="search")])
    session = Session(app)
    cursor = Cursor()
    cursor.apply(await session.greeting())
    return session, form, cursor


class TestTheCursorGoesWhereTheFormThinksItDoes:
    @pytest.mark.parametrize("word", ["ULAN", "ULAN BATOR", "NEW YORK", " ", "A  B"])
    async def test_after_every_letter_of_a_word(self, word: str) -> None:
        session, form, cursor = await a_session()
        for letter in word:
            cursor.apply(await session.receive(letter.encode()))
            assert cursor.at == form.caret, f"after {letter!r} of {word!r}"

    @pytest.mark.parametrize("word", ["ULAN BATOR", "A  B", "NEW YORK"])
    async def test_and_after_rubbing_every_one_of_it_out_again(self, word: str) -> None:
        session, form, cursor = await a_session()
        cursor.apply(await session.receive(word.encode()))
        for letter in reversed(word):
            cursor.apply(await session.receive(b"\x7f"))
            assert cursor.at == form.caret, f"rubbing out {letter!r} of {word!r}"

    async def test_a_space_is_sent_even_though_it_draws_nothing(self) -> None:
        #  The bug itself. A space over a blank leaves the frame identical, so
        #  the repaint had nothing to send and sent nothing -- and the cursor
        #  stayed a cell behind the form for the rest of the word.
        session, form, cursor = await a_session()
        cursor.apply(await session.receive(b"ULAN"))
        before = form.caret
        sent = await session.receive(b" ")
        assert sent, "a space still has to move the cursor"
        cursor.apply(sent)
        assert form.caret[1] == before[1] + 1
        assert cursor.at == form.caret


class TestWhatWasTypedIsWhatIsHeld:
    async def test_a_word_with_a_space_in_it(self) -> None:
        session, form, _ = await a_session()
        await session.receive(b"ULAN BATOR")
        assert form.value == "ULAN BATOR"

    async def test_and_rubbing_out_takes_the_space_like_any_other_cell(self) -> None:
        session, form, _ = await a_session()
        await session.receive(b"ULAN B")
        for _ in range(2):
            await session.receive(b"\x7f")
        assert form.value == "ULAN"
