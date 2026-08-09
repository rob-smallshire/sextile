"""A field a reader types into, and the suggestions beneath it.

The one thing a viewdata page could not previously do: answer a keypress by
changing what is on screen without going anywhere. Everything about how much of
the screen may change, and how often, came off real Commstar in
`docs/spikes/spike_suggestion_block.py`.
"""

from collections.abc import Sequence

import pytest

from sextile import Page, PageAddress, PageFrame, PageRequest, PageRoute, Sextile, keys
from sextile.forms import SUGGESTIONS, Suggest, draw_form
from sextile.session.session import Session
from sextile.templates import Entry, MenuItem
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.frame import Frame

FIELD_ROW = 2
FIRST_ROW = 4

PLACES = [
    ("TRONDHEIM", "NO"),
    ("TROMSO", "NO"),
    ("TRONDHEIMSFJORDEN", "NO"),
    ("TRONDENES", "NO"),
    ("YORK", "GB"),
]


async def look_up(typed: str) -> Sequence[Entry]:
    """A gazetteer small enough to reason about."""
    return [
        MenuItem(name.title(), country, PageAddress(f"32{1000 + n}"))
        for n, (name, country) in enumerate(PLACES)
        if name.startswith(typed)
    ]


def a_field(**wanted: object) -> Suggest:
    return Suggest(
        look_up=look_up,
        field_row=FIELD_ROW,
        first_row=FIRST_ROW,
        label="PLACE:",
        **wanted,  # type: ignore[arg-type]
    )


async def typing(form: Suggest, letters: str) -> Suggest:
    for letter in letters:
        await form.typed(letter)
    return form


def text_of(frame: Frame) -> str:
    characters, _ = frame.to_grid()
    return "\n".join(characters)


class TestTyping:
    async def test_a_letter_goes_into_the_field(self) -> None:
        assert (await typing(a_field(), "TRO")).value == "TRO"

    async def test_letters_are_shouted(self) -> None:
        #  The index they are matched against holds them that way, and a
        #  viewdata keypad has no case to speak of.
        assert (await typing(a_field(), "tro")).value == "TRO"

    async def test_rubbing_out_takes_the_last_one_back(self) -> None:
        form = await typing(a_field(), "TROM")
        await form.typed(keys.RUB_OUT)
        assert form.value == "TRO"

    async def test_rubbing_out_an_empty_field_is_harmless(self) -> None:
        form = a_field()
        await form.typed(keys.RUB_OUT)
        assert form.value == ""


class TestWhichKeysAreTyping:
    @pytest.mark.parametrize("key", ["A", "z", keys.RUB_OUT])
    def test_letters_and_the_rub_out(self, key: str) -> None:
        assert a_field().accepts(key)

    @pytest.mark.parametrize("key", ["1", "9", "0"])
    def test_but_never_a_digit(self, key: str) -> None:
        #  Digits are spoken for by the suggestions. A place whose name holds
        #  one cannot be keyed, which is the trade a numbered list costs.
        assert not a_field().accepts(key)


class TestWhatIsOffered:
    async def test_nothing_typed_offers_nothing(self) -> None:
        #  Rather than the whole gazetteer in whatever order it is held: a
        #  reader who has typed nothing has asked nothing.
        assert a_field().found == ()

    async def test_what_matches_is_offered(self) -> None:
        form = await typing(a_field(), "TROND")
        assert [entry.text for entry in form.found] == [
            "Trondheim",
            "Trondheimsfjorden",
            "Trondenes",
        ]

    async def test_the_digits_lead_to_them(self) -> None:
        form = await typing(a_field(), "YORK")
        assert form.choices() == {"1": PageAddress("321004")}

    async def test_and_no_further_than_the_wire_affords(self) -> None:
        #  Three, measured. A fourth would be a digit that draws a row nobody
        #  can afford to send.
        form = await typing(a_field(), "TRO")
        assert len(form.choices()) == SUGGESTIONS

    async def test_typing_on_narrows_them(self) -> None:
        form = await typing(a_field(), "TROM")
        assert [entry.text for entry in form.found] == ["Tromso"]

    async def test_and_rubbing_out_widens_them_again(self) -> None:
        form = await typing(a_field(), "TROM")
        await form.typed(keys.RUB_OUT)
        assert len(form.found) > 1


class TestDrawing:
    async def test_the_field_shows_what_was_typed(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TROND"))
        assert "PLACE: TROND" in text_of(frame)

    async def test_the_suggestions_are_numbered_beneath_it(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TROND"))
        rows = text_of(frame).splitlines()
        assert "1" in rows[FIRST_ROW] and "Trondheim" in rows[FIRST_ROW]
        assert "2" in rows[FIRST_ROW + 1]

    async def test_a_shorter_suggestion_covers_the_longer_one_it_replaces(self) -> None:
        #  Or a place the reader has typed past goes on offering itself under a
        #  digit that now means something else.
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TROND"))
        draw_form(frame, await typing(a_field(), "TROM"))
        assert "Trondheimsfjorden" not in text_of(frame)

    async def test_nothing_found_says_so(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(empty="No such place."), "ZZZ"))
        assert "No such place." in text_of(frame)

    async def test_the_caret_sits_where_the_next_letter_lands(self) -> None:
        #  Attributes included: each occupies a cell, so counting only the
        #  characters puts the cursor two to the left of the truth.
        frame = Frame()
        form = await typing(a_field(), "TROND")
        draw_form(frame, form)
        row, column = form.caret
        assert frame.text_at(row, column - len("TROND"), len("TROND")) == "TROND"
        assert frame.text_at(row, column, 1) == " ", "and nothing is under it yet"

    async def test_the_page_around_it_is_left_alone(self) -> None:
        frame = Frame()
        Canvas(frame).row(0).text("FIND A PLACE")
        Canvas(frame).row(20).text("SOMETHING ELSE")
        draw_form(frame, await typing(a_field(), "TROND"))
        shown = text_of(frame).splitlines()
        assert "FIND A PLACE" in shown[0]
        assert "SOMETHING ELSE" in shown[20]


class TestThroughASession:
    """What a reader actually experiences, keystroke by keystroke."""

    async def _session(self) -> Session:
        form = a_field()

        async def search(request: PageRequest) -> Page:
            canvas = Canvas()
            canvas.row(0).text("FIND A PLACE")
            draw_form(canvas.frame, form)
            return Page(frames=(PageFrame(frame=canvas.frame, form=form),))

        app = Sextile(
            pages=[
                PageRoute("1", search, name="search"),
                PageRoute("32{n:int}", _somewhere, name="place"),
            ]
        )
        session = Session(app)
        await session.greeting()
        return session

    async def test_a_letter_repaints_rather_than_moving(self) -> None:
        session = await self._session()
        before = session.address
        sent = await session.receive(b"T")
        assert session.address == before, "typing is not going anywhere"
        assert sent, "and something was sent"

    async def test_what_was_typed_reaches_the_screen(self) -> None:
        session = await self._session()
        await session.receive(b"TROND")
        frame = session.current_frame()
        assert frame is not None
        assert "PLACE: TROND" in text_of(frame)

    async def test_a_digit_goes_to_what_it_is_offering(self) -> None:
        session = await self._session()
        await session.receive(b"YORK")
        await session.receive(b"1")
        assert session.address == PageAddress("321004")

    async def test_rubbing_out_reaches_the_form(self) -> None:
        session = await self._session()
        await session.receive(b"TROM")
        await session.receive(b"\x7f")
        frame = session.current_frame()
        assert frame is not None
        assert "PLACE: TRO " in text_of(frame)

    async def test_a_page_request_still_leaves_the_page(self) -> None:
        #  The star is untouched by any of this: a reader is never trapped in a
        #  field they cannot get out of.
        session = await self._session()
        await session.receive(b"TROND")
        await session.receive(b"*321001#")
        assert session.address == PageAddress("321001")

    async def test_only_the_form_s_rows_are_sent(self) -> None:
        #  Not the whole frame, which is eight seconds at 1200 baud against
        #  one for the block.
        session = await self._session()
        await session.receive(b"TRO")
        sent = b"".join(await session.receive(b"N"))
        assert len(sent) < 200, f"a keystroke cost {len(sent)} bytes"

    async def test_and_a_keystroke_that_settles_the_list_costs_less(self) -> None:
        #  Typing on into a list that has narrowed to one leaves the
        #  suggestions alone and repaints the field only.
        session = await self._session()
        await session.receive(b"TROMS")
        settled = b"".join(await session.receive(b"O"))
        assert len(settled) < 60, f"the common keystroke cost {len(settled)} bytes"


async def _somewhere(request: PageRequest, n: int) -> Page:
    return Page(frames=(PageFrame(frame=Canvas().frame),))


class TestTheSecondColumn:
    async def test_the_detail_sits_in_a_column_of_its_own(self) -> None:
        #  Names vary in length, so a detail written straight after one puts
        #  the second column somewhere different on every row. A fixed column
        #  reads as a column -- and a *fixed* one rather than one fitted to the
        #  widest name showing, which would move as the reader types and turn
        #  every keystroke into a repaint of all three rows.
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TRO"))
        rows = text_of(frame).splitlines()
        ends = {row.rstrip().rfind("NO") for row in rows[FIRST_ROW : FIRST_ROW + 3]}
        assert len(ends) == 1, "the countries do not line up"

    async def test_a_long_name_is_shortened_rather_than_the_detail(self) -> None:
        frame = Frame()
        draw_form(frame, await typing(a_field(), "TRONDHEIMS"))
        row = text_of(frame).splitlines()[FIRST_ROW]
        assert "NO" in row, "the detail survives"
        assert "Trondheims" in row, "and as much of the name as fits"
