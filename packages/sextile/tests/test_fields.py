"""A form of several fields, and moving between them.

The interaction is settled by what a viewdata keypad can send, and that is
narrower than it looks. Two of the four arrows carry compass letters on a form
like this -- up arrives as W for West, down as S for South -- which is why the
framework stopped translating arrows at all. TAB shares a byte with cursor
right, measured against Commstar, and is the key a reader reaches for first.
"""

from collections.abc import Callable, Mapping

import pytest

from sextile import Page, PageAddress, PageFrame, PageRequest, PageRoute, Sextile, keys
from sextile.forms import Field, Fields, draw_form
from sextile.session.session import Session
from sextile.viewdata.canvas import Canvas
from sextile.viewdata.frame import Frame

FIRST_ROW = 4
NOTE_ROW = 8


def _takes(hemispheres: str) -> Callable[[str], bool]:
    def takes(key: str) -> bool:
        return key.isdigit() or key in {".", "+", "-", *hemispheres}

    return takes


def where(values: Mapping[str, str]) -> PageAddress | None:
    if not (values["latitude"] and values["longitude"]):
        return None
    return PageAddress("42" + "".join(c for c in "".join(values.values()) if c.isdigit()))


def a_form(**wanted: object) -> Fields:
    return Fields(
        fields=[
            Field("latitude", "LATITUDE", FIRST_ROW, _takes("NS")),
            Field("longitude", "LONGITUDE", FIRST_ROW + 1, _takes("EW")),
        ],
        complete=where,
        **wanted,  # type: ignore[arg-type]
    )


async def typing(form: Fields, keyed: str) -> Fields:
    for key in keyed:
        await form.typed(key)
    return form


def text_of(frame: Frame) -> str:
    characters, _ = frame.to_grid()
    return "\n".join(characters)


class TestTypingIntoOneFieldAtATime:
    async def test_what_is_keyed_goes_into_the_live_field(self) -> None:
        form = await typing(a_form(), "54.0N")
        assert form.values == {"latitude": "54.0N", "longitude": ""}

    async def test_the_first_field_is_live_to_begin_with(self) -> None:
        assert a_form().live.name == "latitude"

    async def test_a_character_the_field_will_not_take_is_refused(self) -> None:
        #  The framework knows about typing; what a latitude is made of is the
        #  service's business, and it says so here.
        assert not a_form().accepts("Q")
        assert a_form().accepts("N")

    async def test_both_ways_of_writing_one_are_taken(self) -> None:
        assert a_form().accepts("-")
        assert a_form().accepts("W") is False, "W is not a latitude"


class TestMovingBetweenThem:
    @pytest.mark.parametrize("key", [keys.RIGHT, keys.DOWN])
    async def test_tab_and_the_forward_arrows_go_on(self, key: str) -> None:
        #  TAB is cursor right on this hardware, measured.
        form = a_form()
        await form.typed(key)
        assert form.live.name == "longitude"

    @pytest.mark.parametrize("key", [keys.LEFT, keys.UP])
    async def test_and_the_others_go_back(self, key: str) -> None:
        form = a_form()
        await form.typed(keys.RIGHT)
        await form.typed(key)
        assert form.live.name == "latitude"

    async def test_going_on_from_the_last_comes_round_to_the_first(self) -> None:
        #  Not up to the end and no further. A reader who tabs into the last
        #  field and wants the first back has nowhere else to go: the back
        #  arrows are there, and nobody who has just learned that TAB moves on
        #  will think to look for them.
        form = a_form()
        await form.typed(keys.RIGHT)
        await form.typed(keys.RIGHT)
        assert form.live.name == "latitude"

    async def test_and_back_from_the_first_comes_round_to_the_last(self) -> None:
        form = a_form()
        await form.typed(keys.LEFT)
        assert form.live.name == "longitude"

    async def test_but_return_does_not_cycle(self) -> None:
        #  TAB moves about a form; RETURN gets to the end of one. If it came
        #  round instead of finishing, a reader could never send anything.
        form = await typing(a_form(), "54.0N")
        form.submit()
        await typing(form, "1.1W")
        assert form.submit() is not None

    async def test_nothing_advances_by_itself(self) -> None:
        #  A field that jumped when it thought it had enough would put the
        #  caret somewhere the reader did not, and with two ways of writing a
        #  coordinate it could not be consistent about when.
        form = await typing(a_form(), "54.0N")
        assert form.live.name == "latitude"

    async def test_rubbing_out_takes_from_the_live_field(self) -> None:
        form = await typing(a_form(), "54.0N")
        await form.typed(keys.RUB_OUT)
        assert form.values["latitude"] == "54.0"


class TestReturn:
    async def test_it_finishes_a_field_and_starts_the_next(self) -> None:
        form = await typing(a_form(), "54.0N")
        assert form.submit() is None
        assert form.live.name == "longitude"

    async def test_and_finishes_the_form_from_the_last(self) -> None:
        form = await typing(a_form(), "54.0N")
        form.submit()
        await typing(form, "1.1W")
        assert form.submit() == PageAddress("4254011")

    async def test_an_incomplete_form_sends_nobody_anywhere(self) -> None:
        form = a_form()
        form.submit()
        assert form.submit() is None


class TestWhatIsOnTheScreen:
    async def test_the_live_field_is_marked_out(self) -> None:
        #  A caret alone would say which, and a caret is one cell of nine
        #  hundred.
        frame = Frame()
        draw_form(frame, a_form())
        _, attributes = frame.to_grid()
        assert "]" in attributes[FIRST_ROW], "a background on the live field"
        assert "]" not in attributes[FIRST_ROW + 1]

    async def test_and_the_mark_moves_with_the_caret(self) -> None:
        frame = Frame()
        form = a_form()
        await form.typed(keys.RIGHT)
        draw_form(frame, form)
        _, attributes = frame.to_grid()
        assert "]" not in attributes[FIRST_ROW]
        assert "]" in attributes[FIRST_ROW + 1]

    async def test_the_values_line_up_whichever_is_live(self) -> None:
        #  Labels differ in length and a background costs three cells, so
        #  without care a value moves sideways when the caret arrives in it.
        form = await typing(a_form(), "54.0N")
        await form.typed(keys.RIGHT)
        await typing(form, "1.1W")
        frame = Frame()
        draw_form(frame, form)
        rows = text_of(frame).splitlines()
        assert rows[FIRST_ROW].index("54.0N") == rows[FIRST_ROW + 1].index("1.1W")

    async def test_the_caret_sits_after_what_was_typed(self) -> None:
        frame = Frame()
        form = await typing(a_form(), "54.0N")
        draw_form(frame, form)
        row, column = form.caret
        assert frame.text_at(row, column - len("54.0N"), len("54.0N")) == "54.0N"

    async def test_a_field_may_explain_itself_while_it_is_live(self) -> None:
        #  A form of several fields has several things to explain and no room
        #  to explain them all at once.
        form = Fields(
            fields=[
                Field("latitude", "LATITUDE", FIRST_ROW, _takes("NS"),
                      hint="54.0N or 54.0"),
                Field("longitude", "LONGITUDE", FIRST_ROW + 1, _takes("EW"),
                      hint="1.1W or -1.1"),
            ],
            complete=where,
            hint_row=NOTE_ROW,
        )
        frame = Frame()
        draw_form(frame, form)
        assert "54.0N" in text_of(frame).splitlines()[NOTE_ROW]
        await form.typed(keys.RIGHT)
        frame = Frame()
        draw_form(frame, form)
        shown = text_of(frame).splitlines()[NOTE_ROW]
        assert "1.1W" in shown
        assert "54.0N" not in shown

    async def test_something_may_be_said_beneath_them(self) -> None:
        async def note(values: Mapping[str, str]) -> str:
            return f"{len(values['latitude'])} keyed"

        frame = Frame()
        draw_form(frame, await typing(a_form(note=note, note_row=NOTE_ROW), "54"))
        assert "2 keyed" in text_of(frame).splitlines()[NOTE_ROW]


class TestThroughASession:
    async def _session(self) -> tuple[Session, Fields]:
        form = a_form()

        async def position(request: PageRequest) -> Page:
            canvas = Canvas()
            draw_form(canvas.frame, form)
            return Page(frames=(PageFrame(frame=canvas.frame, form=form),))

        app = Sextile(
            pages=[
                PageRoute("4", position, name="position"),
                PageRoute("42{n:int}", _somewhere, name="point"),
            ]
        )
        #  A service starts at page 1 unless told otherwise, and the form is
        #  at 4.
        session = Session(app, start=PageAddress("4"))
        await session.greeting()
        return session, form

    async def test_a_reader_tabs_and_keys_and_arrives(self) -> None:
        session, _ = await self._session()
        await session.receive(b"54.0N")
        await session.receive(b"\x09")  # TAB
        await session.receive(b"1.1W")
        await session.receive(b"\x5f")  # RETURN
        assert session.address == PageAddress("4254011")

    async def test_the_up_arrow_does_not_type_a_west(self) -> None:
        #  The whole reason the framework stopped translating arrows. Up
        #  arrives as W, and W is West.
        session, form = await self._session()
        await session.receive(b"\x09")
        await session.receive(bytes([0x0B]))  # up arrow
        assert form.values["longitude"] == ""
        assert form.live.name == "latitude"

    async def test_moving_between_fields_moves_the_cursor(self) -> None:
        #  Nothing on the rows need change when the caret moves, so the reply
        #  would be empty if the session did not place it deliberately.
        session, _ = await self._session()
        assert b"".join(await session.receive(b"\x09"))


async def _somewhere(request: PageRequest, n: int) -> Page:
    return Page(frames=(PageFrame(frame=Canvas().frame),))
